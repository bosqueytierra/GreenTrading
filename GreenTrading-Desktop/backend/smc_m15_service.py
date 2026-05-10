#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GreenTrading Desktop - SMC M15 Service
Phase 3: SMC analysis service for dashboard

CORRECCIÓN FASE 3: Implementación directa de lógica SMC
NO depende de analyze_smc - toda la lógica está contenida aquí

Analyzes market data using SMC engines to provide:
- H1 trend
- M15 trend
- Last M15 event (BOS/CHOCH)
- Mother zone M15
- Score calculation
- OB/FVG/Barrida detection
- Setup state (ACTIVA/SIN_SETUP)
"""

import traceback
from datetime import datetime, timezone
import pandas as pd

from core.state_machine import (
    M1_VELAS_ZONA,
    LLEGANDO_A_ZONA_MINUTOS_UMBRAL,
    log_price_entered_zone_check,
    log_profit_transition_check,
    calcular_velocidad_m1_hacia_zona,
    calcular_estado_dashboard,
    calcular_transicion_estado,
    calcular_estado_historial,
)

from strategies.smc_m15_pro import (
    SMCM15ProEngine,
    direccion_operativa_por_indice,
    validar_zona_operativa,
    detectar_swings,
    detectar_estructura,
    detectar_fvg,
    buscar_order_block,
    detectar_barrida_previa,
    crear_zona_m15,
    calcular_niveles_operativos,
    format_trend,
    get_last_event,
)

# CRITICAL LOG: Confirm which file is being executed
print("SMC_SERVICE_PATH:", __file__)

# Import Supabase service
try:
    import supabase_service
except ImportError:
    print("WARNING: Supabase service not available")
    supabase_service = None

# Configuration
SWING_LOOKBACK = 3
CLOSE_BREAK = True
# M1_VELAS_ZONA and LLEGANDO_A_ZONA_MINUTOS_UMBRAL are imported from core.state_machine

# =========================
# SMART SYNC / DEBOUNCE
# =========================

# Global cache para último estado de cada símbolo
# Key: symbol, Value: dict con campos críticos
_setup_cache = {}


def log_fresh_master_style_zone(symbol: str, precio_actual: float, zona_fresca: dict) -> None:
    """
    Log obligatorio: zona fresca calculada al estilo master_bot.
    """
    zona_desde = None
    zona_hasta = None
    entrada = None
    stoploss = None
    evento = None
    score = None
    es_util = None

    if zona_fresca:
        zona_desde = zona_fresca.get('zona_desde')
        zona_hasta = zona_fresca.get('zona_hasta')
        direccion_fresca = zona_fresca.get(
            'direccion_operativa',
            zona_fresca.get('direccion', direccion_operativa_por_indice(symbol) or 'ALCISTA')
        )
        try:
            niveles_frescos = calcular_niveles_operativos(zona_fresca, direccion_fresca)
            entrada = niveles_frescos.get('entrada')
            stoploss = niveles_frescos.get('stoploss')
        except Exception:
            entrada = None
            stoploss = None
        evento = zona_fresca.get('evento')
        score = zona_fresca.get('score')
        es_util = zona_fresca.get('es_util')

    print(f"\nFRESH_MASTER_STYLE_ZONE:")
    print(f"  symbol: {symbol}")
    print(f"  precio_actual: {precio_actual}")
    print(f"  zona_desde: {zona_desde}")
    print(f"  zona_hasta: {zona_hasta}")
    print(f"  entrada: {entrada}")
    print(f"  stoploss: {stoploss}")
    print(f"  evento: {evento}")
    print(f"  score: {score}")
    print(f"  es_util: {es_util}")


def log_tracked_supabase_zone(
    symbol: str,
    estado_previo: str,
    zona_desde: float,
    zona_hasta: float,
    entrada: float,
    stoploss: float,
    created_at: str,
    updated_at: str
) -> None:
    """
    Log obligatorio: zona activa recuperada desde Supabase.
    """
    print(f"\nTRACKED_SUPABASE_ZONE:")
    print(f"  symbol: {symbol}")
    print(f"  estado_previo: {estado_previo}")
    print(f"  zona_desde: {zona_desde}")
    print(f"  zona_hasta: {zona_hasta}")
    print(f"  entrada: {entrada}")
    print(f"  stoploss: {stoploss}")
    print(f"  created_at: {created_at}")
    print(f"  updated_at: {updated_at}")

def _has_relevant_changes(symbol: str, new_data: dict) -> bool:
    """
    Determina si hay cambios relevantes que justifiquen un UPDATE en Supabase.
    
    Solo actualiza si cambian campos críticos:
    - estado
    - entrada
    - stoploss
    - tp_1_1
    - score
    - zona_desde/zona_hasta
    - precio (cambio significativo >1%)
    
    Args:
        symbol: Symbol name
        new_data: Nuevo setup data con campos críticos
    
    Returns:
        True si hay cambios relevantes, False si no
    """
    if symbol not in _setup_cache:
        # Primera vez: siempre sincronizar
        _setup_cache[symbol] = new_data
        return True
    
    old_data = _setup_cache[symbol]
    
    # Campos críticos para comparar
    critical_fields = [
        'estado',
        'entrada',
        'stoploss',
        'tp_1_1',
        'score',
        'zona_desde',
        'zona_hasta'
    ]
    
    # Verificar cambios en campos críticos
    for field in critical_fields:
        if old_data.get(field) != new_data.get(field):
            print(f"SYNC TRIGGER: {symbol} - {field} changed from {old_data.get(field)} to {new_data.get(field)}")
            _setup_cache[symbol] = new_data
            return True
    
    # Verificar cambio significativo en precio (>1%)
    old_price = old_data.get('precio_actual', 0)
    new_price = new_data.get('precio_actual', 0)
    if old_price > 0:
        price_change_pct = abs(new_price - old_price) / old_price * 100
        if price_change_pct > 1.0:
            print(f"SYNC TRIGGER: {symbol} - price changed {price_change_pct:.2f}%")
            _setup_cache[symbol] = new_data
            return True
    
    # No hay cambios relevantes
    return False


def sync_setup_to_supabase(analysis_result: dict) -> None:
    """
    Sincroniza setup con Supabase solo si hay cambios relevantes.
    
    Implementa smart sync / debounce:
    - Solo actualiza cuando cambian campos críticos
    - Evita spam updates innecesarios
    - Cache de estado previo por símbolo
    
    Args:
        analysis_result: Resultado de analyze_symbol_smc()
    """
    if not supabase_service:
        print("  SUPABASE SYNC: Service not available")
        return
    
    # Skip SIN SETUP / SIN_SETUP
    estado_actual = analysis_result.get('estado', '')
    if estado_actual in ('SIN SETUP', 'SIN_SETUP'):
        print(f"  SUPABASE SYNC: Skipping {analysis_result.get('symbol')} - SIN_SETUP no se guarda en historial")
        return
    
    # Skip si faltan campos requeridos
    if not analysis_result.get('entrada') or not analysis_result.get('stoploss'):
        print(f"  SUPABASE SYNC: Skipping {analysis_result.get('symbol')} - falta entrada o stoploss")
        return
    
    symbol = analysis_result['symbol']
    
    # Preparar datos críticos para comparación
    critical_data = {
        'estado': analysis_result.get('estado_historial', analysis_result.get('estado_dashboard', 'ESPERANDO_ENTRADA')),
        'entrada': analysis_result.get('entrada'),
        'stoploss': analysis_result.get('stoploss'),
        'tp_1_1': analysis_result.get('tp_1_1'),
        'score': analysis_result.get('score', 0),
        'zona_desde': analysis_result.get('zona_madre_m15', {}).get('desde', 0),
        'zona_hasta': analysis_result.get('zona_madre_m15', {}).get('hasta', 0),
        'precio_actual': analysis_result.get('price')
    }
    
    # Verificar si hay cambios relevantes
    if not _has_relevant_changes(symbol, critical_data):
        # No hay cambios, skip sync
        print(f"  SUPABASE SYNC: Skipping {symbol} - no hay cambios relevantes")
        return
    
    print(f"  SUPABASE SYNC: Preparing sync for {symbol} - cambios detectados")
    
    # Hay cambios: preparar setup data completo
    setup_data = {
        'strategy_id': 'SMC_M15_PRO',
        'strategy_name': 'SMC M15 PRO',
        'symbol': symbol,
        'tendencia_h1': analysis_result.get('tendencia_h1', '--'),
        'tendencia_m15': analysis_result.get('tendencia_m15', '--'),
        'ultimo_evento_m15': analysis_result.get('ultimo_evento_m15', '--'),
        'entrada': critical_data['entrada'],
        'stoploss': critical_data['stoploss'],
        'tp_1_1': critical_data['tp_1_1'],
        'score': critical_data['score'],
        'ob': analysis_result.get('ob') in ['SÍ', 'SI', 'YES'],
        'fvg': analysis_result.get('fvg') in ['SÍ', 'SI', 'YES'],
        'barrida': analysis_result.get('barrida') in ['SÍ', 'SI', 'YES'],
        'estado': critical_data['estado'],
        'estado_dashboard': analysis_result.get('estado_dashboard', 'ESPERANDO_ENTRADA'),
        'precio_detectado': critical_data['precio_actual'],
        'precio_actual': critical_data['precio_actual']
    }
    
    # Buscar setup activo existente
    existing = supabase_service.get_active_setup(
        setup_data['strategy_id'],
        setup_data['symbol'],
        setup_data['entrada'],
        setup_data['stoploss']
    )
    
    if existing:
        # Update existente
        setup_id = existing['id']
        updates = {
            'estado': setup_data['estado'],
            'estado_dashboard': setup_data['estado_dashboard'],
            'precio_actual': setup_data['precio_actual']
        }
        print(f"  SUPABASE SYNC: UPDATE intent para {symbol}, id={setup_id}, estado={setup_data['estado']}")
        result = supabase_service.update_setup(setup_id, updates)
        if result:
            print(f"SUPABASE SYNC: Updated {symbol}")
        else:
            print(f"SUPABASE SYNC WARNING: update_setup devolvio None para {symbol}")
    else:
        closed_setup = None
        if (
            hasattr(supabase_service, "get_closed_setup_by_levels")
            and setup_data.get('tp_1_1') is not None
        ):
            closed_setup = supabase_service.get_closed_setup_by_levels(
                setup_data['strategy_id'],
                setup_data['symbol'],
                setup_data['entrada'],
                setup_data['stoploss'],
                setup_data['tp_1_1']
            )

        decision = "SKIP_ALREADY_CLOSED" if closed_setup else "CREATE_NEW"
        print(f"\nDUPLICATE_CLOSED_ZONE_CHECK:")
        print(f"  symbol: {setup_data['symbol']}")
        print(f"  strategy_id: {setup_data['strategy_id']}")
        print(f"  entrada: {setup_data['entrada']}")
        print(f"  stoploss: {setup_data['stoploss']}")
        print(f"  tp_1_1: {setup_data['tp_1_1']}")
        print(f"  found_closed_setup: {bool(closed_setup)}")
        print(f"  closed_estado: {closed_setup.get('estado') if closed_setup else None}")
        print(f"  closed_id: {closed_setup.get('id') if closed_setup else None}")
        print(f"  decision: {decision}")

        if closed_setup:
            analysis_result["zona_madre_m15"] = {"desde": 0, "hasta": 0}
            analysis_result["entrada"] = None
            analysis_result["stoploss"] = None
            analysis_result["tp_1_1"] = None
            analysis_result["score"] = 0
            analysis_result["ob"] = "NO"
            analysis_result["fvg"] = "NO"
            analysis_result["barrida"] = "NO"
            analysis_result["estado_dashboard"] = "SIN_SETUP"
            analysis_result["estado_historial"] = "SIN_SETUP"
            analysis_result["estado_final"] = "SIN_SETUP"
            analysis_result["estado"] = "SIN SETUP"
            _setup_cache[symbol] = {
                'estado': 'SIN_SETUP',
                'entrada': None,
                'stoploss': None,
                'tp_1_1': None,
                'score': 0,
                'zona_desde': 0,
                'zona_hasta': 0,
                'precio_actual': analysis_result.get('price')
            }
            print(f"  SUPABASE SYNC: SKIP create_setup para {symbol} - zona ya cerrada (TP/SL)")
            return

        # Create nuevo
        print(f"  SUPABASE SYNC: INSERT intent para {symbol} (nuevo setup)")
        result = supabase_service.create_setup(setup_data)
        if result:
            print(f"SUPABASE SYNC: Created {symbol}")
        else:
            print(f"SUPABASE SYNC WARNING: create_setup devolvio None para {symbol}")


# =========================
# BOOM / CRASH FILTERING
# =========================

def direccion_operativa_por_indice(symbol):
    """
    Determina la dirección operativa según el tipo de índice.
    
    Args:
        symbol: Symbol name
    
    Returns:
        "ALCISTA" for Boom indices
        "BAJISTA" for Crash indices
        None for other symbols
    """
    if "Boom" in symbol:
        return "ALCISTA"
    if "Crash" in symbol:
        return "BAJISTA"
    return None


def validar_zona_operativa(symbol, zona, precio_actual):
    """
    Valida si una zona es operativa según el tipo de índice.
    
    Args:
        symbol: Symbol name
        zona: Zone dictionary with zona_desde and zona_hasta
        precio_actual: Current price
    
    Returns:
        Tuple (es_util, motivo, direccion_operativa)
    """
    direccion_operativa = direccion_operativa_por_indice(symbol)

    if direccion_operativa == "ALCISTA":
        es_util = zona["zona_hasta"] <= precio_actual
        motivo = "Boom busca reacción alcista: la zona debe estar bajo el precio actual."
    elif direccion_operativa == "BAJISTA":
        es_util = zona["zona_desde"] >= precio_actual
        motivo = "Crash busca reacción bajista: la zona debe estar sobre el precio actual."
    else:
        es_util = True
        motivo = "Índice no clasificado como Boom/Crash."

    return es_util, motivo, direccion_operativa


# =========================
# SWINGS DETECTION
# =========================

def detectar_swings(df, lookback=SWING_LOOKBACK):
    """
    Detecta swing highs y swing lows en el DataFrame.
    
    Args:
        df: DataFrame with columns ['high', 'low', 'time']
        lookback: Number of candles to consider before and after
    
    Returns:
        List of dictionaries with detected swings
    """
    swings = []

    for i in range(lookback, len(df) - lookback):
        high = df["high"].iloc[i]
        low = df["low"].iloc[i]

        prev_highs = df["high"].iloc[i-lookback:i]
        next_highs = df["high"].iloc[i+1:i+1+lookback]

        prev_lows = df["low"].iloc[i-lookback:i]
        next_lows = df["low"].iloc[i+1:i+1+lookback]

        if high > prev_highs.max() and high > next_highs.max():
            swings.append({
                "index": i,
                "time": df["time"].iloc[i],
                "tipo": "HIGH",
                "precio": float(high)
            })

        if low < prev_lows.min() and low < next_lows.min():
            swings.append({
                "index": i,
                "time": df["time"].iloc[i],
                "tipo": "LOW",
                "precio": float(low)
            })

    return swings


# =========================
# STRUCTURE DETECTION
# =========================

def detectar_estructura(df, swings):
    """
    Detecta estructura de mercado: BOS (Break of Structure) y CHOCH (Change of Character).
    
    Args:
        df: DataFrame with columns ['close', 'high', 'low', 'time']
        swings: List of detected swings
    
    Returns:
        Tuple (eventos, tendencia_actual)
    """
    eventos = []
    tendencia = None
    ultimo_high = None
    ultimo_low = None
    niveles_rotos = set()

    for i in range(len(df)):
        close = float(df["close"].iloc[i])
        high = float(df["high"].iloc[i])
        low = float(df["low"].iloc[i])
        time = df["time"].iloc[i]

        swings_pasados = [s for s in swings if s["index"] < i]

        highs = [s for s in swings_pasados if s["tipo"] == "HIGH"]
        lows = [s for s in swings_pasados if s["tipo"] == "LOW"]

        if highs:
            ultimo_high = highs[-1]

        if lows:
            ultimo_low = lows[-1]

        if not ultimo_high or not ultimo_low:
            continue

        rompe_high = close > ultimo_high["precio"] if CLOSE_BREAK else high > ultimo_high["precio"]
        rompe_low = close < ultimo_low["precio"] if CLOSE_BREAK else low < ultimo_low["precio"]

        high_key = ("HIGH", ultimo_high["index"])
        low_key = ("LOW", ultimo_low["index"])

        if rompe_high and high_key not in niveles_rotos:
            if tendencia in [None, "ALCISTA"]:
                evento = "BOS_ALCISTA"
                tendencia = "ALCISTA"
            else:
                evento = "CHOCH_ALCISTA"
                tendencia = "ALCISTA"

            eventos.append({
                "time": time,
                "index": i,
                "evento": evento,
                "nivel_roto": ultimo_high["precio"],
                "precio_cierre": close
            })

            niveles_rotos.add(high_key)

        elif rompe_low and low_key not in niveles_rotos:
            if tendencia in [None, "BAJISTA"]:
                evento = "BOS_BAJISTA"
                tendencia = "BAJISTA"
            else:
                evento = "CHOCH_BAJISTA"
                tendencia = "BAJISTA"

            eventos.append({
                "time": time,
                "index": i,
                "evento": evento,
                "nivel_roto": ultimo_low["precio"],
                "precio_cierre": close
            })

            niveles_rotos.add(low_key)

    return eventos, tendencia


# =========================
# FVG (Fair Value Gaps)
# =========================

def detectar_fvg(df):
    """
    Detecta Fair Value Gaps (FVG) - huecos dejados por movimientos impulsivos.
    
    FVG Alcista: low actual > high de hace 2 velas
    FVG Bajista: high actual < low de hace 2 velas
    
    Args:
        df: DataFrame with columns ['high', 'low', 'time']
    
    Returns:
        List of detected FVGs
    """
    fvgs = []

    for i in range(2, len(df)):
        vela_1 = df.iloc[i-2]
        vela_3 = df.iloc[i]

        if vela_3["low"] > vela_1["high"]:
            fvgs.append({
                "index": i,
                "time": df["time"].iloc[i],
                "tipo": "FVG_ALCISTA",
                "desde": float(vela_1["high"]),
                "hasta": float(vela_3["low"])
            })

        if vela_3["high"] < vela_1["low"]:
            fvgs.append({
                "index": i,
                "time": df["time"].iloc[i],
                "tipo": "FVG_BAJISTA",
                "desde": float(vela_3["high"]),
                "hasta": float(vela_1["low"])
            })

    return fvgs


# =========================
# ORDER BLOCKS
# =========================

def buscar_order_block(df, evento):
    """
    Busca el Order Block asociado a un evento de estructura.
    
    Order Block Alcista: última vela bajista antes del impulso alcista
    Order Block Bajista: última vela alcista antes del impulso bajista
    
    Args:
        df: DataFrame with candle data
        evento: Dictionary with event information
    
    Returns:
        Dictionary with Order Block data or None
    """
    idx = evento["index"]
    direccion = "ALCISTA" if "ALCISTA" in evento["evento"] else "BAJISTA"

    inicio = max(0, idx - 20)
    tramo = df.iloc[inicio:idx]

    if direccion == "ALCISTA":
        candidatas = tramo[tramo["close"] < tramo["open"]]
        if candidatas.empty:
            return None

        ob = candidatas.iloc[-1]
        return {
            "tipo": "OB_ALCISTA",
            "time": ob["time"],
            "desde": float(ob["low"]),
            "hasta": float(ob["high"])
        }
    else:
        candidatas = tramo[tramo["close"] > tramo["open"]]
        if candidatas.empty:
            return None

        ob = candidatas.iloc[-1]
        return {
            "tipo": "OB_BAJISTA",
            "time": ob["time"],
            "desde": float(ob["low"]),
            "hasta": float(ob["high"])
        }


# =========================
# SWEEP / BARRIDA
# =========================

def detectar_barrida_previa(df, evento, direccion, lookback=40):
    """
    Detecta barridas de liquidez previas al evento.
    
    Args:
        df: DataFrame with candle data
        evento: Structure event
        direccion: "ALCISTA" or "BAJISTA"
        lookback: Number of candles to review backwards
    
    Returns:
        Dictionary with sweep data or None
    """
    idx = evento["index"]
    inicio = max(0, idx - lookback)
    tramo = df.iloc[inicio:idx].copy()

    if len(tramo) < 10:
        return None

    if direccion == "ALCISTA":
        for j in range(5, len(tramo)):
            minimo_anterior = tramo["low"].iloc[:j].min()
            vela = tramo.iloc[j]

            if vela["low"] < minimo_anterior and vela["close"] > minimo_anterior:
                return {
                    "time": vela["time"],
                    "tipo": "BARRIDA_BAJISTA_PREVIA",
                    "nivel": float(minimo_anterior),
                    "low": float(vela["low"]),
                    "close": float(vela["close"])
                }
    else:
        for j in range(5, len(tramo)):
            maximo_anterior = tramo["high"].iloc[:j].max()
            vela = tramo.iloc[j]

            if vela["high"] > maximo_anterior and vela["close"] < maximo_anterior:
                return {
                    "time": vela["time"],
                    "tipo": "BARRIDA_ALCISTA_PREVIA",
                    "nivel": float(maximo_anterior),
                    "high": float(vela["high"]),
                    "close": float(vela["close"])
                }

    return None


# =========================
# M15 ZONE CREATION
# =========================

def crear_zona_m15(df_m15, eventos_m15, fvgs_m15, symbol, precio_actual):
    """
    Construye la zona M15 combinando:
    - Ultimo evento de estructura
    - Order Block
    - Fair Value Gap
    - Barrida previa
    
    Calcula un score de confluencia basado en los elementos presentes.
    Valida que la zona sea operativa según el tipo de índice.
    
    Args:
        df_m15: DataFrame M15
        eventos_m15: List of M15 structure events
        fvgs_m15: List of M15 FVGs
        symbol: Symbol name
        precio_actual: Current price
    
    Returns:
        Dictionary with complete zone or None
    """
    if not eventos_m15:
        return None

    direccion_operativa = direccion_operativa_por_indice(symbol)
    eventos_filtrados = []

    # Filter events by operational direction
    for evento in eventos_m15:
        direccion_evento = "ALCISTA" if "ALCISTA" in evento["evento"] else "BAJISTA"
        if direccion_operativa and direccion_evento != direccion_operativa:
            continue
        eventos_filtrados.append(evento)

    if not eventos_filtrados:
        return None

    # Try to create zone from last filtered event
    for ultimo_evento in reversed(eventos_filtrados):
        direccion = "ALCISTA" if "ALCISTA" in ultimo_evento["evento"] else "BAJISTA"

        ob = buscar_order_block(df_m15, ultimo_evento)

        fvgs_validos = [
            f for f in fvgs_m15
            if f["index"] <= ultimo_evento["index"]
            and (
                (direccion == "ALCISTA" and f["tipo"] == "FVG_ALCISTA") or
                (direccion == "BAJISTA" and f["tipo"] == "FVG_BAJISTA")
            )
        ]

        fvg = fvgs_validos[-1] if fvgs_validos else None
        barrida = detectar_barrida_previa(df_m15, ultimo_evento, direccion)

        zona_desde = None
        zona_hasta = None

        if ob and fvg:
            zona_desde = min(ob["desde"], fvg["desde"], fvg["hasta"])
            zona_hasta = max(ob["hasta"], fvg["desde"], fvg["hasta"])
        elif ob:
            zona_desde = ob["desde"]
            zona_hasta = ob["hasta"]
        elif fvg:
            zona_desde = min(fvg["desde"], fvg["hasta"])
            zona_hasta = max(fvg["desde"], fvg["hasta"])

        if zona_desde is None:
            continue

        zona = {
            "direccion": direccion,
            "evento": ultimo_evento,
            "ob": ob,
            "fvg": fvg,
            "barrida": barrida,
            "zona_desde": zona_desde,
            "zona_hasta": zona_hasta,
            "score": 0
        }

        es_util, motivo, direccion_op = validar_zona_operativa(symbol, zona, precio_actual)

        score = 0
        if "CHOCH" in ultimo_evento["evento"]:
            score += 3
        if "BOS" in ultimo_evento["evento"]:
            score += 2
        if ob:
            score += 2
        if fvg:
            score += 2
        if barrida:
            score += 3
        if es_util:
            score += 2

        zona["score"] = score
        zona["es_util"] = es_util
        zona["motivo"] = motivo
        zona["direccion_operativa"] = direccion_op

        print("\nEVALUATING ZONE:")
        print(f"  symbol: {symbol}")
        print(f"  zona_desde: {zona_desde}")
        print(f"  zona_hasta: {zona_hasta}")
        print(f"  precio_actual: {precio_actual}")
        print(f"  direccion: {direccion}")
        print(f"  es_util: {es_util}")
        print(f"  motivo: {motivo}")

        if not es_util:
            print("ZONE REJECTED: es_util=False")
            continue

        print("ZONE ACCEPTED: es_util=True")
        print(f"  score: {score}")
        return zona

    return None


# =========================
# NIVELES OPERATIVOS Y ESTADOS
# =========================

def calcular_niveles_operativos(zona: dict, direccion_operativa: str) -> dict:
    """
    Calcula entrada, stoploss y tp_1_1 según la zona y dirección.
    
    Args:
        zona: Zona con zona_desde y zona_hasta
        direccion_operativa: "ALCISTA" o "BAJISTA"
    
    Returns:
        dict con entrada, stoploss, tp_1_1
    """
    zona_desde = zona.get("zona_desde", 0)
    zona_hasta = zona.get("zona_hasta", 0)
    zona_size = abs(zona_hasta - zona_desde)
    
    if direccion_operativa == "ALCISTA":
        # Para ALCISTA (Boom): entrada arriba, SL abajo
        entrada = zona_hasta
        stoploss = zona_desde
        tp_1_1 = entrada + zona_size  # Proyección 1:1 hacia arriba
    else:
        # Para BAJISTA (Crash): entrada abajo, SL arriba
        entrada = zona_desde
        stoploss = zona_hasta
        tp_1_1 = entrada - zona_size  # Proyección 1:1 hacia abajo
    
    return {
        "entrada": round(entrada, 2),
        "stoploss": round(stoploss, 2),
        "tp_1_1": round(tp_1_1, 2)
    }


# calcular_velocidad_m1_hacia_zona, calcular_estado_dashboard,
# calcular_transicion_estado, calcular_estado_historial
# are imported from core.state_machine above.


# =========================
# MAIN ANALYSIS FUNCTION
# =========================

def analyze_symbol_smc(symbol: str, df_h1: pd.DataFrame, df_m15: pd.DataFrame, df_m1: pd.DataFrame = None) -> dict:
    """
    Public compatibility facade for SMC_M15_PRO analysis.

    Flow:
    1. Load/receive data (already provided in args)
    2. Delegate strategic logic to SMCM15ProEngine.analyze(...)
    3. Sync resulting setup to Supabase (smart sync)
    4. Return unchanged payload shape
    """
    engine = SMCM15ProEngine()

    result = engine.analyze(
        symbol=symbol,
        df_h1=df_h1,
        df_m15=df_m15,
        df_m1=df_m1,
        supabase_service=supabase_service,
        create_sin_setup_response=create_sin_setup_response,
        print_result_summary=print_result_summary,
    )

    if (
        result.get('estado') not in ('SIN SETUP', 'SIN_SETUP')
        and result.get('entrada') is not None
        and result.get('stoploss') is not None
    ):
        sync_setup_to_supabase(result)

    return result


def create_sin_setup_response(symbol: str, price: float = None) -> dict:
    """
    Create a minimal response when analysis cannot be performed at all
    (no data, etc.)
    
    This is different from having no zone - when there's no zone but
    analysis runs, we still return trends and events.
    
    Args:
        symbol: Symbol name
        price: Current price (optional)
    
    Returns:
        dict with minimal structure
    """
    return {
        "symbol": symbol,
        "price": price,
        "tendencia_h1": "--",
        "tendencia_m15": "--",
        "ultimo_evento_m15": "--",
        "zona_madre_m15": {"desde": 0, "hasta": 0},
        "entrada": None,
        "stoploss": None,
        "tp_1_1": None,
        "score": 0,
        "ob": "NO",
        "fvg": "NO",
        "barrida": "NO",
        "estado_dashboard": "SIN_SETUP",
        "estado_historial": "SIN_SETUP",
        "estado_final": "SIN_SETUP",
        "estado": "SIN SETUP",
        "updated_at": datetime.now(timezone.utc).isoformat()
    }


def format_trend(trend: str) -> str:
    """Format trend name"""
    if trend is None:
        return "--"
    return trend.upper()


def get_last_event(eventos: list) -> str:
    """
    Get last M15 event (BOS or CHOCH)
    
    Args:
        eventos: List of structure events
    
    Returns:
        Event string (BOS_ALCISTA, CHOCH_BAJISTA, etc.)
    """
    if not eventos or len(eventos) == 0:
        return "--"
    
    # Get last event
    last = eventos[-1]
    
    # Events have 'evento' field: BOS_ALCISTA, CHOCH_BAJISTA, etc.
    evento = last.get('evento', '')
    
    if evento:
        return evento.upper()
    
    return "--"


def print_result_summary(result: dict):
    """Print formatted result summary for logging"""
    print(f"\n  RESULT SUMMARY:")
    print(f"     Symbol: {result['symbol']}")
    print(f"     Tendencia H1: {result['tendencia_h1']}")
    print(f"     Tendencia M15: {result['tendencia_m15']}")
    print(f"     Ultimo Evento M15: {result['ultimo_evento_m15']}")
    print(f"     Zona: {result['zona_madre_m15']['desde']:.2f} - {result['zona_madre_m15']['hasta']:.2f}")
    print(f"     Score: {result['score']}")
    print(f"     OB: {result['ob']}, FVG: {result['fvg']}, Barrida: {result['barrida']}")
    print(f"     Estado: {result['estado']}")
    print(f"{'='*60}\n")
