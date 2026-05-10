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

import sys
import os
from datetime import datetime, timezone
import pandas as pd

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
M1_VELAS_ZONA = 15
LLEGANDO_A_ZONA_MINUTOS_UMBRAL = 5.0  # Tiempo estimado (en minutos) por debajo del cual se clasifica LLEGANDO_A_ZONA

# =========================
# SMART SYNC / DEBOUNCE
# =========================

# Global cache para último estado de cada símbolo
# Key: symbol, Value: dict con campos críticos
_setup_cache = {}


def log_price_entered_zone_check(
    symbol: str,
    precio_actual: float,
    entrada: float,
    stoploss: float,
    zona_desde: float,
    zona_hasta: float,
    direccion_operativa: str,
    en_zona_operativa: bool,
    estado_antes: str,
    estado_despues: str
) -> None:
    """Log obligatorio para validar prioridad de EN_ZONA."""
    print("\nPRICE ENTERED ZONE CHECK")
    print(f"  symbol: {symbol if symbol else '?'}")
    print(f"  precio_actual: {precio_actual}")
    print(f"  entrada: {entrada}")
    print(f"  stoploss: {stoploss}")
    print(f"  zona_desde: {zona_desde}")
    print(f"  zona_hasta: {zona_hasta}")
    print(f"  direccion_operativa: {direccion_operativa}")
    print(f"  en_zona_operativa: {en_zona_operativa}")
    print(f"  estado_antes: {estado_antes}")
    print(f"  estado_despues: {estado_despues}")


def log_profit_transition_check(
    symbol: str,
    estado_previo: str,
    precio_actual: float,
    entrada: float,
    stoploss: float,
    tp_1_1: float,
    direccion: str,
    en_zona: bool,
    salio_a_favor: bool,
    toco_tp: bool,
    toco_sl: bool,
    estado_final: str
) -> None:
    """Log obligatorio para EN_ZONA -> PROFIT -> TP/SL."""
    print("\nPROFIT_TRANSITION_CHECK")
    print(f"  symbol: {symbol if symbol else '?'}")
    print(f"  estado_previo: {estado_previo}")
    print(f"  precio_actual: {precio_actual}")
    print(f"  entrada: {entrada}")
    print(f"  stoploss: {stoploss}")
    print(f"  tp_1_1: {tp_1_1}")
    print(f"  direccion: {direccion}")
    print(f"  en_zona: {en_zona}")
    print(f"  salio_a_favor: {salio_a_favor}")
    print(f"  toco_tp: {toco_tp}")
    print(f"  toco_sl: {toco_sl}")
    print(f"  estado_final: {estado_final}")


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


def calcular_velocidad_m1_hacia_zona(df_m1, entrada, direccion, min_velas=3, lookback=None):
    """
    Calcula la velocidad promedio (puntos/minuto) de las velas M1 que avanzan hacia la zona.

    Para BOOM (ALCISTA): velas bajistas (close < open) empujan el precio hacia la entrada (abajo).
    Para CRASH (BAJISTA): velas alcistas (close > open) empujan el precio hacia la entrada (arriba).

    Args:
        df_m1: DataFrame de velas M1 (columnas: open, close, high, low)
        entrada: Precio de entrada de la zona
        direccion: "ALCISTA" o "BAJISTA"
        min_velas: Minimo de velas direccionales requeridas (defecto 3)
        lookback: Cuantas velas M1 recientes analizar (defecto M1_VELAS_ZONA)

    Returns:
        dict con:
            cantidad_velas: int  -- velas que avanzan hacia la zona
            velocidad: float     -- puntos por minuto promedio
            suficientes: bool    -- True si hay al menos min_velas
    """
    if lookback is None:
        lookback = M1_VELAS_ZONA

    if df_m1 is None or len(df_m1) == 0:
        return {"cantidad_velas": 0, "velocidad": 0.0, "suficientes": False}

    df_recent = df_m1.tail(lookback)

    if direccion == "ALCISTA":
        # BOOM: velas bajistas (close < open) empujan precio hacia la entrada (abajo)
        mask = df_recent["close"] < df_recent["open"]
        movimientos = (df_recent.loc[mask, "open"] - df_recent.loc[mask, "close"]).tolist()
    else:
        # CRASH: velas alcistas (close > open) empujan precio hacia la entrada (arriba)
        mask = df_recent["close"] > df_recent["open"]
        movimientos = (df_recent.loc[mask, "close"] - df_recent.loc[mask, "open"]).tolist()

    cantidad = len(movimientos)
    if cantidad < min_velas:
        return {"cantidad_velas": cantidad, "velocidad": 0.0, "suficientes": False}

    velocidad = sum(movimientos) / cantidad
    return {"cantidad_velas": cantidad, "velocidad": velocidad, "suficientes": True}


def calcular_estado_dashboard(
    precio_actual: float,
    entrada: float,
    zona_desde: float,
    zona_hasta: float,
    direccion: str,
    df_m1=None,
    symbol: str = ""
) -> str:
    """
    Calcula el estado del dashboard segun la posicion del precio.

    Reglas por direccion:

    BAJISTA (Crash):
        - entrada = zona_desde (borde inferior), stoploss = zona_hasta (borde superior)
        - El precio debe venir desde ABAJO para buscar la zona
        - Si precio > zona_hasta: SIN_SETUP (precio sobre stoploss, zona invalida)
        - Si zona_desde <= precio <= zona_hasta: EN_ZONA
        - Si precio < zona_desde: ACTIVA o LLEGANDO_A_ZONA segun velocidad M1
        - PROFIT: calculado solo por la maquina de estados (requiere haber pasado por EN_ZONA)

    ALCISTA (Boom):
        - entrada = zona_hasta (borde superior), stoploss = zona_desde (borde inferior)
        - El precio debe venir desde ARRIBA para buscar la zona
        - Si precio < zona_desde: SIN_SETUP (precio bajo stoploss, zona invalida)
        - Si zona_desde <= precio <= zona_hasta: EN_ZONA
        - Si precio > zona_hasta: ACTIVA o LLEGANDO_A_ZONA segun velocidad M1
        - PROFIT: calculado solo por la maquina de estados (requiere haber pasado por EN_ZONA)

    LLEGANDO_A_ZONA: se determina por velocidad M1 hacia la zona.
        distancia_a_entrada / velocidad_m1_hacia_zona <= 5 minutos => LLEGANDO_A_ZONA
        Si no hay suficientes velas M1 direccionales => ACTIVA (no inventar LLEGANDO_A_ZONA)

    Args:
        precio_actual: Precio actual
        entrada: Precio de entrada (zona_desde para Crash, zona_hasta para Boom)
        zona_desde: Limite inferior de zona
        zona_hasta: Limite superior de zona
        direccion: "ALCISTA" o "BAJISTA"
        df_m1: DataFrame de velas M1 recientes (opcional)
        symbol: Nombre del simbolo para logs (opcional)

    Returns:
        Estado dashboard: SIN_SETUP | EN_ZONA | ACTIVA | LLEGANDO_A_ZONA
    """
    # EN_ZONA tiene prioridad absoluta:
    # BOOM (ALCISTA): stoploss <= precio_actual <= entrada
    # CRASH (BAJISTA): entrada <= precio_actual <= stoploss
    if direccion == "ALCISTA":
        en_zona_operativa = zona_desde <= precio_actual <= entrada
    else:
        en_zona_operativa = entrada <= precio_actual <= zona_hasta

    estado_despues_check = "EN_ZONA" if en_zona_operativa else "CONTINUA_EVALUACION"
    log_price_entered_zone_check(
        symbol=symbol,
        precio_actual=precio_actual,
        entrada=entrada,
        stoploss=zona_desde if direccion == "ALCISTA" else zona_hasta,
        zona_desde=zona_desde,
        zona_hasta=zona_hasta,
        direccion_operativa=direccion,
        en_zona_operativa=en_zona_operativa,
        estado_antes="CALCULANDO_DASHBOARD",
        estado_despues=estado_despues_check
    )

    if en_zona_operativa:
        return "EN_ZONA"

    if direccion == "ALCISTA":
        # Boom: precio se acerca desde ARRIBA.
        # Si esta por debajo del stoploss (zona_desde), la zona es invalida.
        if precio_actual < zona_desde:
            return "SIN_SETUP"
        # precio_actual > zona_hasta: acercandose desde arriba
        distancia = precio_actual - zona_hasta
        stoploss_log = zona_desde
    else:
        # BAJISTA (Crash): precio se acerca desde ABAJO.
        # Si esta por encima del stoploss (zona_hasta), la zona es invalida.
        if precio_actual > zona_hasta:
            return "SIN_SETUP"
        # precio_actual < zona_desde: acercandose desde abajo
        distancia = zona_desde - precio_actual
        stoploss_log = zona_hasta

    # Clasificar usando velocidad M1 hacia la zona
    vel_result = calcular_velocidad_m1_hacia_zona(df_m1, entrada, direccion)
    cantidad_velas = vel_result["cantidad_velas"]
    velocidad = vel_result["velocidad"]
    suficientes = vel_result["suficientes"]

    if suficientes and velocidad > 0:
        tiempo_estimado = distancia / velocidad
        estado_resultado = "LLEGANDO_A_ZONA" if tiempo_estimado <= LLEGANDO_A_ZONA_MINUTOS_UMBRAL else "ACTIVA"
    else:
        tiempo_estimado = None
        estado_resultado = "ACTIVA"

    # Log requerido por especificacion
    sym_label = symbol if symbol else "?"
    print(f"\n--- LLEGANDO_A_ZONA EVAL [{sym_label}] ---")
    print(f"  precio_actual: {precio_actual}")
    print(f"  entrada: {entrada}")
    print(f"  stoploss: {stoploss_log}")
    print(f"  distancia_a_entrada: {round(distancia, 4)}")
    print(f"  cantidad_velas_m1_hacia_zona: {cantidad_velas}")
    print(f"  velocidad_m1_hacia_zona: {round(velocidad, 4)} pts/min")
    if tiempo_estimado is not None:
        print(f"  tiempo_estimado_min: {round(tiempo_estimado, 2)}")
    else:
        print(f"  tiempo_estimado_min: N/A (sin velas suficientes)")
    print(f"  estado_dashboard: {estado_resultado}")
    print(f"---------------------------------------------")

    return estado_resultado


def calcular_transicion_estado(
    symbol: str,
    estado_previo: str,
    estado_calculado: str,
    precio_actual: float,
    entrada: float,
    stoploss: float,
    tp: float,
    zona_desde: float,
    zona_hasta: float
) -> tuple:
    """
    Calcula la transición de estado válida basada en el estado previo.
    
    MÁQUINA DE ESTADOS CORRECTA:
    
    ESPERANDO_ENTRADA <-> LLEGANDO_A_ZONA (pueden oscilar)
    ESPERANDO_ENTRADA -> EN_ZONA
    LLEGANDO_A_ZONA -> EN_ZONA
    
    EN_ZONA -> PROFIT (salida favorable)
    EN_ZONA -> SL (toca stoploss)
    EN_ZONA -> EN_ZONA (se mantiene)
    
    PROFIT -> TP (alcanza 1:1)
    PROFIT -> SL (retrocede a stoploss)
    PROFIT -> PROFIT (se mantiene)
    
    TP, SL, DESCARTADA = terminales (no cambian)
    
    REGLA CLAVE:
    - Una vez EN_ZONA, NUNCA vuelve a: ESPERANDO_ENTRADA, LLEGANDO_A_ZONA, ACTIVA
    - Una vez PROFIT, NUNCA vuelve a: EN_ZONA, ESPERANDO_ENTRADA, LLEGANDO_A_ZONA, ACTIVA
    
    Args:
        symbol: Symbol name
        estado_previo: Estado guardado previamente (None si es nueva zona)
        estado_calculado: Estado calculado por lógica actual
        precio_actual: Precio actual
        entrada: Precio de entrada
        stoploss: Stop loss
        tp: Take profit 1:1
        zona_desde: Límite inferior de zona
        zona_hasta: Límite superior de zona
    
    Returns:
        tuple (estado_final, motivo_transicion)
    """
    direccion = "ALCISTA" if entrada > stoploss else "BAJISTA"
    en_zona_operativa = (
        (direccion == "ALCISTA" and stoploss <= precio_actual <= entrada) or
        (direccion == "BAJISTA" and entrada <= precio_actual <= stoploss)
    )
    salio_a_favor = (
        (direccion == "ALCISTA" and precio_actual > entrada) or
        (direccion == "BAJISTA" and precio_actual < entrada)
    )
    toco_tp = (
        (direccion == "ALCISTA" and precio_actual >= tp) or
        (direccion == "BAJISTA" and precio_actual <= tp)
    )
    toco_sl = (
        (direccion == "ALCISTA" and precio_actual <= stoploss) or
        (direccion == "BAJISTA" and precio_actual >= stoploss)
    )
    
    estado_antes_check = estado_previo if estado_previo else estado_calculado
    estado_despues_check = "EN_ZONA" if en_zona_operativa else estado_calculado
    log_price_entered_zone_check(
        symbol=symbol,
        precio_actual=precio_actual,
        entrada=entrada,
        stoploss=stoploss,
        zona_desde=zona_desde,
        zona_hasta=zona_hasta,
        direccion_operativa=direccion,
        en_zona_operativa=en_zona_operativa,
        estado_antes=estado_antes_check,
        estado_despues=estado_despues_check
    )

    def finalizar(estado_final: str, motivo: str) -> tuple:
        log_profit_transition_check(
            symbol=symbol,
            estado_previo=estado_previo,
            precio_actual=precio_actual,
            entrada=entrada,
            stoploss=stoploss,
            tp_1_1=tp,
            direccion=direccion,
            en_zona=en_zona_operativa,
            salio_a_favor=salio_a_favor,
            toco_tp=toco_tp,
            toco_sl=toco_sl,
            estado_final=estado_final
        )
        return estado_final, motivo

    # CHECK 1: Si NO hay estado previo, solo permitir ACTIVA/ESPERANDO_ENTRADA
    if not estado_previo:
        if estado_calculado == 'SIN_SETUP':
            return finalizar("SIN_SETUP", "Zona invalida: precio fuera del rango valido para esta direccion")
        if en_zona_operativa:
            return finalizar("EN_ZONA", "Nueva zona detectada (precio dentro de zona)")
        if toco_tp:
            return finalizar("ACTIVA", "Nueva zona detectada (precio en TP, requiere monitoreo)")
        elif toco_sl:
            return finalizar("ACTIVA", "Nueva zona detectada (precio en SL, requiere monitoreo)")
        elif estado_calculado in ['ACTIVA', 'ESPERANDO_ENTRADA', 'LLEGANDO_A_ZONA']:
            return finalizar(estado_calculado, "Nueva zona detectada")
        elif estado_calculado == 'EN_ZONA':
            return finalizar("ACTIVA", "Nueva zona detectada (calculado EN_ZONA, sin historial previo)")
        elif estado_calculado == 'PROFIT':
            return finalizar("ACTIVA", "Nueva zona detectada (precio en profit, sin historial previo)")
        else:
            return finalizar("ACTIVA", "Nueva zona detectada")

    if estado_previo in ['TP', 'SL']:
        return finalizar(estado_previo, f"Estado terminal {estado_previo} (no cambia)")

    if estado_previo == 'PROFIT':
        if toco_tp:
            return finalizar("TP", "Take Profit alcanzado")
        if toco_sl:
            return finalizar("SL", "Stop Loss alcanzado")
        return finalizar("PROFIT", "Mantiene profit (esperando TP o SL)")

    if estado_previo == 'EN_ZONA':
        if toco_sl:
            return finalizar("SL", "Stop Loss alcanzado")
        if salio_a_favor:
            return finalizar("PROFIT", "Precio salio en direccion favorable")
        if en_zona_operativa:
            return finalizar("EN_ZONA", "Precio sigue en zona")
        return finalizar("EN_ZONA", "Zona mantiene memoria (sin regreso a estados previos)")

    if estado_previo in ['ACTIVA', 'ESPERANDO_ENTRADA', 'LLEGANDO_A_ZONA']:
        if en_zona_operativa or estado_calculado == 'EN_ZONA':
            log_price_entered_zone_check(
                symbol=symbol,
                precio_actual=precio_actual,
                entrada=entrada,
                stoploss=stoploss,
                zona_desde=zona_desde,
                zona_hasta=zona_hasta,
                direccion_operativa=direccion,
                en_zona_operativa=en_zona_operativa,
                estado_antes=estado_previo,
                estado_despues="EN_ZONA"
            )
            return finalizar("EN_ZONA", "Precio tocó la zona")
        elif estado_calculado == 'PROFIT':
            return finalizar(estado_previo, f"Mantiene {estado_previo} (no puede saltar a PROFIT sin pasar por EN_ZONA)")
        elif toco_sl:
            return finalizar("SL", "Stop Loss alcanzado")
        else:
            return finalizar(estado_calculado, f"Transición desde {estado_previo}")

    if toco_sl:
        return finalizar("SL", "Stop Loss alcanzado")

    return finalizar(estado_calculado, f"Transición estándar desde {estado_previo}")


def calcular_estado_historial(
    symbol: str,
    estado_dashboard: str,
    precio_actual: float,
    entrada: float,
    stoploss: float,
    tp: float,
    zona_desde: float,
    zona_hasta: float,
    estado_previo: str = None
) -> tuple:
    """
    Calcula estado historial validando transiciones correctas.
    
    CORRECCIÓN CRÍTICA: Ahora usa estado previo guardado para validar
    que las transiciones sean correctas según la máquina de estados.
    
    Estados historial:
    - ACTIVA/ESPERANDO_ENTRADA: Estados iniciales para nuevas zonas
    - LLEGANDO_A_ZONA: Acercándose a zona
    - EN_ZONA: En zona (solo si antes estuvo ACTIVA)
    - PROFIT: En ganancia flotante (solo si antes estuvo EN_ZONA)
    - TP: Take profit alcanzado (solo si antes estuvo EN_ZONA o PROFIT)
    - SL: Stop loss alcanzado (solo si antes estuvo ACTIVA o EN_ZONA)
    
    Args:
        symbol: Symbol name
        estado_dashboard: Estado calculado por lógica de distancia
        precio_actual: Precio actual
        entrada: Precio de entrada
        stoploss: Stop loss
        tp: Take profit 1:1
        zona_desde: Límite inferior de zona
        zona_hasta: Límite superior de zona
        estado_previo: Estado guardado previamente en Supabase (None si nueva zona)
    
    Returns:
        tuple (estado_final, motivo_transicion)
    """
    # Calcular estado según lógica de precios
    estado_calculado = estado_dashboard
    
    # Calcular transición válida
    estado_final, motivo = calcular_transicion_estado(
        symbol,
        estado_previo,
        estado_calculado,
        precio_actual,
        entrada,
        stoploss,
        tp,
        zona_desde,
        zona_hasta
    )
    
    return estado_final, motivo


# =========================
# MAIN ANALYSIS FUNCTION
# =========================

def analyze_symbol_smc(symbol: str, df_h1: pd.DataFrame, df_m15: pd.DataFrame, df_m1: pd.DataFrame = None) -> dict:
    """
    Analyze a symbol using direct SMC implementation.
    
    FASE 3 CORRECCIÓN: NO usa analyze_smc - implementa directamente la lógica.
    
    Flujo:
    1. Calcular SIEMPRE swings y estructura para H1 y M15
    2. Obtener tendencia_h1, tendencia_m15, ultimo_evento_m15
    3. Intentar crear zona (opcional)
    4. Si NO hay zona: devolver estructura con SIN SETUP
    5. Si hay zona: devolver estructura con zona y score
    
    Args:
        symbol: Symbol name
        df_h1: H1 candles DataFrame
        df_m15: M15 candles DataFrame
        df_m1: M1 candles DataFrame (opcional, para calcular velocidad LLEGANDO_A_ZONA)
    
    Returns:
        dict with SMC analysis results
    """
    # Log symbol processing
    print(f"\n{'='*60}")
    print(f"Analyzing {symbol}")
    print(f"{'='*60}")
    
    # If no data, return minimal response
    if df_h1 is None or df_m15 is None or len(df_h1) == 0 or len(df_m15) == 0:
        print(f"  ERROR No data available for {symbol}")
        print(f"     H1 candles: {len(df_h1) if df_h1 is not None else 0}")
        print(f"     M15 candles: {len(df_m15) if df_m15 is not None else 0}")
        return create_sin_setup_response(symbol)
    
    print(f"  OK Data loaded:")
    print(f"    - H1 candles: {len(df_h1)}")
    print(f"    - M15 candles: {len(df_m15)}")
    
    try:
        # ===================================================================
        # NIVEL A: ESTRUCTURA BASE (SIEMPRE SE CALCULA)
        # ===================================================================
        print(f"  Calculating base structure...")
        
        # Calculate swings
        swings_h1 = detectar_swings(df_h1, SWING_LOOKBACK)
        swings_m15 = detectar_swings(df_m15, SWING_LOOKBACK)
        print(f"    - H1 swings: {len(swings_h1)}")
        print(f"    - M15 swings: {len(swings_m15)}")
        
        # Calculate structure (eventos + tendencia)
        eventos_h1, tendencia_h1 = detectar_estructura(df_h1, swings_h1)
        eventos_m15, tendencia_m15 = detectar_estructura(df_m15, swings_m15)
        print(f"    - H1 eventos: {len(eventos_h1)}, tendencia: {tendencia_h1}")
        print(f"    - M15 eventos: {len(eventos_m15)}, tendencia: {tendencia_m15}")
        
        # Get last M15 event (always calculate)
        ultimo_evento_m15 = get_last_event(eventos_m15)
        print(f"    - Ultimo evento M15: {ultimo_evento_m15}")
        
        # Get current price
        precio_actual = float(df_m15["close"].iloc[-1])
        print(f"    - Precio actual: {precio_actual}")
        
        # ===================================================================
        # NIVEL B: SETUP/ZONA
        # Reglas de prioridad:
        #   1) EN_ZONA / PROFIT: mantener zona guardada
        #   2) ACTIVA / ESPERANDO_ENTRADA / LLEGANDO_A_ZONA:
        #      comparar con zona fresca estilo master_bot y reemplazar si difiere
        #   3) Sin setup activo: usar zona fresca estilo master_bot
        # ===================================================================

        # Estados no terminales que activan MODO SEGUIMIENTO
        ESTADOS_SEGUIMIENTO = {'ACTIVA', 'ESPERANDO_ENTRADA', 'LLEGANDO_A_ZONA', 'EN_ZONA', 'PROFIT'}
        # Sub-clasificación para la lógica de zona en MODO SEGUIMIENTO
        ESTADOS_PRE_ZONA  = {'ACTIVA', 'ESPERANDO_ENTRADA', 'LLEGANDO_A_ZONA'}
        ESTADOS_POST_ZONA = {'EN_ZONA', 'PROFIT'}

        setup_activo = None
        if supabase_service:
            setup_activo = supabase_service.get_active_setup_by_symbol('SMC_M15_PRO', symbol)

        # Determinar si aplica MODO SEGUIMIENTO y extraer datos guardados
        modo_seguimiento = False
        if setup_activo and setup_activo.get('estado') in ESTADOS_SEGUIMIENTO:
            estado_previo = setup_activo.get('estado')
            entrada = setup_activo.get('entrada')
            stoploss = setup_activo.get('stoploss')
            tp_1_1 = setup_activo.get('tp_1_1')

            if entrada is None or stoploss is None or tp_1_1 is None:
                print(f"  WARNING MODO SEGUIMIENTO: datos incompletos en setup guardado ({symbol})")
                print(f"    entrada={entrada}, stoploss={stoploss}, tp_1_1={tp_1_1}")
                print(f"    Forzando MODO BUSQUEDA")
            else:
                modo_seguimiento = True

        if modo_seguimiento:
            # ---------------------------------------------------------------
            # MODO SEGUIMIENTO: zona guardada como punto de partida
            # Se divide en dos sub-modos según el estado previo:
            #   PRE-ZONA  (ACTIVA/ESPERANDO_ENTRADA/LLEGANDO_A_ZONA):
            #     - recalcular candidata con crear_zona_m15
            #     - reemplazar si la nueva zona es distinta y válida
            #   POST-ZONA (EN_ZONA/PROFIT):
            #     - bloquear zona guardada sin recalcular
            # ---------------------------------------------------------------

            # Inferir direccion_operativa desde el simbolo
            direccion_operativa = direccion_operativa_por_indice(symbol)
            if not direccion_operativa:
                # Fallback: inferir por entrada vs stoploss
                direccion_operativa = "ALCISTA" if entrada > stoploss else "BAJISTA"

            # Reconstruir zona_desde/zona_hasta (inverso de calcular_niveles_operativos)
            if direccion_operativa == "ALCISTA":
                # entrada = zona_hasta, stoploss = zona_desde
                zona_desde = stoploss
                zona_hasta = entrada
            else:
                # entrada = zona_desde, stoploss = zona_hasta
                zona_desde = entrada
                zona_hasta = stoploss

            # Recuperar ob/fvg/barrida/score almacenados (pueden ser bool o string)
            has_ob = bool(setup_activo.get('ob', False))
            has_fvg = bool(setup_activo.get('fvg', False))
            has_barrida = bool(setup_activo.get('barrida', False))
            score = setup_activo.get('score', 0) or 0

            log_tracked_supabase_zone(
                symbol=symbol,
                estado_previo=estado_previo,
                zona_desde=zona_desde,
                zona_hasta=zona_hasta,
                entrada=entrada,
                stoploss=stoploss,
                created_at=setup_activo.get('created_at'),
                updated_at=setup_activo.get('updated_at')
            )

            # Calcular SIEMPRE zona fresca estilo master_bot para logging/comparación
            fvgs_m15_seg = detectar_fvg(df_m15)
            zona_fresca_master = crear_zona_m15(df_m15, eventos_m15, fvgs_m15_seg, symbol, precio_actual)
            log_fresh_master_style_zone(symbol, precio_actual, zona_fresca_master)

            print(f"  MODO SEGUIMIENTO: usando zona guardada para {symbol}")
            print(f"    estado_previo: {estado_previo}")
            print(f"    entrada: {entrada}, stoploss: {stoploss}, tp_1_1: {tp_1_1}")
            print(f"    zona_desde: {zona_desde}, zona_hasta: {zona_hasta}")
            print(f"    direccion_operativa: {direccion_operativa}")

            # ------------------------------------------------------------------
            # PRE-ZONA: comparar zona guardada vs zona fresca estilo master_bot
            # ------------------------------------------------------------------
            if estado_previo in ESTADOS_PRE_ZONA:
                print(f"  MODO SEGUIMIENTO PRE-ZONA: comparando zona guardada vs zona fresca para {symbol}...")

                # ----------------------------------------------------------
                # PRIORIDAD ABSOLUTA: detectar toque de zona guardada ANTES
                # de cualquier reemplazo.
                # BOOM (ALCISTA): stoploss <= precio_actual <= entrada
                # CRASH (BAJISTA): entrada <= precio_actual <= stoploss
                # ----------------------------------------------------------
                en_zona_actual = (
                    (direccion_operativa == "ALCISTA" and stoploss <= precio_actual <= entrada) or
                    (direccion_operativa == "BAJISTA" and entrada <= precio_actual <= stoploss)
                )

                print(f"\n=== CHECK_TRACKED_ZONE_TOUCH_BEFORE_REPLACE ===")
                print(f"  symbol: {symbol}")
                print(f"  estado_previo: {estado_previo}")
                print(f"  precio_actual: {precio_actual}")
                print(f"  entrada_actual: {entrada}")
                print(f"  stoploss_actual: {stoploss}")
                print(f"  en_zona_actual: {en_zona_actual}")
                print(f"===============================================\n")

                if en_zona_actual:
                    # Precio ya toco la zona guardada: bloquear y marcar EN_ZONA.
                    # NO recalcular ni reemplazar zona.
                    print(f"\n=== ZONE_TOUCH_LOCKED ===")
                    print(f"  symbol: {symbol}")
                    print(f"  estado_previo: {estado_previo}")
                    print(f"  nuevo_estado: EN_ZONA")
                    print(f"  entrada: {entrada}")
                    print(f"  stoploss: {stoploss}")
                    print(f"=========================\n")

                    estado_dashboard = "EN_ZONA"
                    log_price_entered_zone_check(
                        symbol=symbol,
                        precio_actual=precio_actual,
                        entrada=entrada,
                        stoploss=stoploss,
                        zona_desde=zona_desde,
                        zona_hasta=zona_hasta,
                        direccion_operativa=direccion_operativa,
                        en_zona_operativa=True,
                        estado_antes=estado_previo,
                        estado_despues=estado_dashboard
                    )
                    print(f"  MODO SEGUIMIENTO PRE-ZONA: EN_ZONA bloqueado por toque de zona guardada")

                    # Calcular estado historial con maquina de estados
                    estado_historial, motivo_transicion = calcular_estado_historial(
                        symbol,
                        estado_dashboard,
                        precio_actual,
                        entrada,
                        stoploss,
                        tp_1_1,
                        zona_desde,
                        zona_hasta,
                        estado_previo
                    )
                    print(f"  Estado Historial (validado, ZONE_TOUCH_LOCKED): {estado_historial}")
                    print(f"  Motivo transicion: {motivo_transicion}")

                    print(f"\n=== LOG TRANSICION ESTADO {symbol} (ZONE_TOUCH_LOCKED) ===")
                    print(f"  symbol: {symbol}")
                    print(f"  estado_previo: {estado_previo}")
                    print(f"  estado_calculado: {estado_dashboard}")
                    print(f"  estado_validado: {estado_historial}")
                    print(f"  precio_actual: {precio_actual}")
                    print(f"  zona_desde: {zona_desde}")
                    print(f"  zona_hasta: {zona_hasta}")
                    print(f"  entrada: {entrada}")
                    print(f"  stoploss: {stoploss}")
                    print(f"  tp_1_1: {tp_1_1}")
                    print(f"  motivo_transicion: {motivo_transicion}")
                    print(f"======================================================\n")

                    print(f"\n=== RESUMEN SETUP {symbol} (ZONE_TOUCH_LOCKED) ===")
                    print(f"  zona_madre_m15: desde={zona_desde}, hasta={zona_hasta}")
                    print(f"  score: {score}")
                    print(f"  ob: {'SI' if has_ob else 'NO'}")
                    print(f"  fvg: {'SI' if has_fvg else 'NO'}")
                    print(f"  barrida: {'SI' if has_barrida else 'NO'}")
                    print(f"  estado_final: {estado_historial}")
                    print(f"  guardado_historial: SI (ZONE_TOUCH_LOCKED, zona activa)")
                    print(f"=================================================\n")

                    result = {
                        "symbol": symbol,
                        "price": precio_actual,
                        "tendencia_h1": format_trend(tendencia_h1),
                        "tendencia_m15": format_trend(tendencia_m15),
                        "ultimo_evento_m15": ultimo_evento_m15,
                        "zona_madre_m15": {
                            "desde": float(zona_desde),
                            "hasta": float(zona_hasta)
                        },
                        "entrada": entrada,
                        "stoploss": stoploss,
                        "tp_1_1": tp_1_1,
                        "estado_dashboard": estado_dashboard,
                        "estado_historial": estado_historial,
                        "estado_final": estado_historial,
                        "score": score,
                        "ob": "SI" if has_ob else "NO",
                        "fvg": "SI" if has_fvg else "NO",
                        "barrida": "SI" if has_barrida else "NO",
                        "estado": estado_historial,
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }
                    print_result_summary(result)
                    sync_setup_to_supabase(result)
                    return result

                # NO toco la zona guardada: ahora si comparar con zona fresca.
                if zona_fresca_master:
                    dir_cand = zona_fresca_master.get('direccion_operativa', zona_fresca_master.get('direccion', direccion_operativa))
                    niv_cand = calcular_niveles_operativos(zona_fresca_master, dir_cand)
                    entrada_nueva   = niv_cand["entrada"]
                    stoploss_nueva  = niv_cand["stoploss"]
                    tp_nueva        = niv_cand["tp_1_1"]
                    z_desde_nueva   = float(zona_fresca_master.get('zona_desde', 0))
                    z_hasta_nueva   = float(zona_fresca_master.get('zona_hasta', 0))
                    es_util_nueva   = bool(zona_fresca_master.get('es_util', False))
                    score_nueva     = zona_fresca_master.get('score', 0)

                    # Log NEW_CANDIDATE_ZONE (obligatorio)
                    print(f"\n=== NEW_CANDIDATE_ZONE ===")
                    print(f"  symbol: {symbol}")
                    print(f"  entrada_nueva: {entrada_nueva}")
                    print(f"  stoploss_nueva: {stoploss_nueva}")
                    print(f"  zona_desde_nueva: {z_desde_nueva}")
                    print(f"  zona_hasta_nueva: {z_hasta_nueva}")
                    print(f"  es_util: {es_util_nueva}")
                    print(f"  score: {score_nueva}")
                    print(f"==========================\n")

                    # Reemplazar si la zona fresca (estilo master_bot) es útil y distinta.
                    zona_cambio = (
                        es_util_nueva and
                        (
                            round(entrada_nueva, 2) != round(entrada, 2) or
                            round(stoploss_nueva, 2) != round(stoploss, 2) or
                            round(z_desde_nueva, 2) != round(zona_desde, 2) or
                            round(z_hasta_nueva, 2) != round(zona_hasta, 2)
                        )
                    )
                    if zona_cambio:
                        # Log ZONE_REPLACED_BEFORE_TOUCH (obligatorio)
                        print(f"\n=== ZONE_REPLACED_BEFORE_TOUCH ===")
                        print(f"  symbol: {symbol}")
                        print(f"  motivo: nueva_zona_mas_reciente_es_util")
                        print(f"  entrada_anterior: {entrada}")
                        print(f"  entrada_nueva: {entrada_nueva}")
                        print(f"  stoploss_anterior: {stoploss}")
                        print(f"  stoploss_nueva: {stoploss_nueva}")
                        print(f"==================================\n")

                        # Reemplazar variables de zona
                        entrada          = entrada_nueva
                        stoploss         = stoploss_nueva
                        tp_1_1           = tp_nueva
                        zona_desde       = z_desde_nueva
                        zona_hasta       = z_hasta_nueva
                        direccion_operativa = dir_cand
                        has_ob           = zona_fresca_master.get('ob') is not None
                        has_fvg          = zona_fresca_master.get('fvg') is not None
                        has_barrida      = zona_fresca_master.get('barrida') is not None
                        score            = score_nueva

                        # Actualizar setup activo en Supabase con la zona fresca elegida
                        if supabase_service and setup_activo and setup_activo.get('id'):
                            updates_zona_fresca = {
                                'entrada': entrada,
                                'stoploss': stoploss,
                                'tp_1_1': tp_1_1,
                                'score': score,
                                'ob': has_ob,
                                'fvg': has_fvg,
                                'barrida': has_barrida
                            }
                            print(f"  SUPABASE SYNC: actualizando setup activo con zona fresca (id={setup_activo.get('id')})")
                            supabase_service.update_setup(setup_activo.get('id'), updates_zona_fresca)
                    else:
                        print(f"  PRE-ZONA: zona guardada se mantiene (zona fresca coincide o no es_util).")
                else:
                    print(f"  PRE-ZONA: no se encontro zona fresca valida, manteniendo zona guardada.")

            # ------------------------------------------------------------------
            # POST-ZONA: bloquear zona guardada (EN_ZONA / PROFIT)
            # ------------------------------------------------------------------
            elif estado_previo in ESTADOS_POST_ZONA:
                # Log ZONE_LOCKED_AFTER_EN_ZONA (obligatorio)
                print(f"\n=== ZONE_LOCKED_AFTER_EN_ZONA ===")
                print(f"  symbol: {symbol}")
                print(f"  estado_previo: {estado_previo}")
                print(f"  entrada: {entrada}")
                print(f"  stoploss: {stoploss}")
                print(f"=================================\n")

            # EN_ZONA tiene prioridad absoluta en MODO SEGUIMIENTO
            en_zona_seguimiento = (
                (direccion_operativa == "ALCISTA" and stoploss <= precio_actual <= entrada) or
                (direccion_operativa == "BAJISTA" and entrada <= precio_actual <= stoploss)
            )

            if en_zona_seguimiento:
                estado_dashboard = "EN_ZONA"
                log_price_entered_zone_check(
                    symbol=symbol,
                    precio_actual=precio_actual,
                    entrada=entrada,
                    stoploss=stoploss,
                    zona_desde=zona_desde,
                    zona_hasta=zona_hasta,
                    direccion_operativa=direccion_operativa,
                    en_zona_operativa=en_zona_seguimiento,
                    estado_antes=estado_previo if estado_previo else "MODO_SEGUIMIENTO",
                    estado_despues=estado_dashboard
                )
                print(f"  MODO SEGUIMIENTO: EN_ZONA forzado por rango operativo guardado")
            else:
                # Calcular estado dashboard con la zona guardada
                estado_dashboard = calcular_estado_dashboard(
                    precio_actual,
                    entrada,
                    zona_desde,
                    zona_hasta,
                    direccion_operativa,
                    df_m1=df_m1,
                    symbol=symbol
                )
            print(f"  Estado Dashboard (calculado, MODO SEGUIMIENTO): {estado_dashboard}")

            # Calcular estado historial con maquina de estados
            estado_historial, motivo_transicion = calcular_estado_historial(
                symbol,
                estado_dashboard,
                precio_actual,
                entrada,
                stoploss,
                tp_1_1,
                zona_desde,
                zona_hasta,
                estado_previo
            )
            print(f"  Estado Historial (validado, MODO SEGUIMIENTO): {estado_historial}")
            print(f"  Motivo transicion: {motivo_transicion}")

            # LOG transicion
            print(f"\n=== LOG TRANSICION ESTADO {symbol} (MODO SEGUIMIENTO) ===")
            print(f"  symbol: {symbol}")
            print(f"  estado_previo: {estado_previo}")
            print(f"  estado_calculado: {estado_dashboard}")
            print(f"  estado_validado: {estado_historial}")
            print(f"  precio_actual: {precio_actual}")
            print(f"  zona_desde: {zona_desde}")
            print(f"  zona_hasta: {zona_hasta}")
            print(f"  entrada: {entrada}")
            print(f"  stoploss: {stoploss}")
            print(f"  tp_1_1: {tp_1_1}")
            print(f"  motivo_transicion: {motivo_transicion}")
            print(f"======================================================\n")

            print(f"\n=== RESUMEN SETUP {symbol} (MODO SEGUIMIENTO) ===")
            print(f"  zona_madre_m15: desde={zona_desde}, hasta={zona_hasta}")
            print(f"  score: {score}")
            print(f"  ob: {'SI' if has_ob else 'NO'}")
            print(f"  fvg: {'SI' if has_fvg else 'NO'}")
            print(f"  barrida: {'SI' if has_barrida else 'NO'}")
            print(f"  estado_final: {estado_historial}")
            print(f"  guardado_historial: SI (MODO SEGUIMIENTO, zona activa)")
            print(f"=================================================\n")

            result = {
                "symbol": symbol,
                "price": precio_actual,
                "tendencia_h1": format_trend(tendencia_h1),
                "tendencia_m15": format_trend(tendencia_m15),
                "ultimo_evento_m15": ultimo_evento_m15,
                "zona_madre_m15": {
                    "desde": float(zona_desde),
                    "hasta": float(zona_hasta)
                },
                "entrada": entrada,
                "stoploss": stoploss,
                "tp_1_1": tp_1_1,
                "estado_dashboard": estado_dashboard,
                "estado_historial": estado_historial,
                "estado_final": estado_historial,
                "score": score,
                "ob": "SÍ" if has_ob else "NO",
                "fvg": "SÍ" if has_fvg else "NO",
                "barrida": "SÍ" if has_barrida else "NO",
                "estado": estado_historial,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            print_result_summary(result)
            sync_setup_to_supabase(result)
            return result

        # ---------------------------------------------------------------
        # MODO BUSQUEDA: no hay setup activo, buscar zona nueva
        # ---------------------------------------------------------------
        print(f"  MODO BUSQUEDA: buscando zona nueva para {symbol}...")
        log_tracked_supabase_zone(
            symbol=symbol,
            estado_previo="NINGUNO",
            zona_desde=None,
            zona_hasta=None,
            entrada=None,
            stoploss=None,
            created_at=None,
            updated_at=None
        )

        # Detect FVGs
        fvgs_m15 = detectar_fvg(df_m15)
        print(f"    - FVGs M15: {len(fvgs_m15)}")

        # Try to create zone
        zona = crear_zona_m15(df_m15, eventos_m15, fvgs_m15, symbol, precio_actual)
        log_fresh_master_style_zone(symbol, precio_actual, zona)
        
        # If NO zone, return BASE STRUCTURE with SIN SETUP for zone part
        if not zona:
            print(f"  WARNING NO ZONE created (no OB/FVG or not operative)")
            print(f"  Returning BASE STRUCTURE with SIN SETUP")
            
            # COMPREHENSIVE LOG as requested in problem statement
            print(f"\n=== RESUMEN SETUP {symbol} ===")
            print(f"  zona_madre_m15: NINGUNA")
            print(f"  score: 0")
            print(f"  ob: NO")
            print(f"  fvg: NO")
            print(f"  barrida: NO")
            print(f"  es_util: N/A")
            print(f"  estado_final: SIN SETUP")
            print(f"  guardado_historial: NO (sin zona valida)")
            print(f"===============================\n")
            
            result = {
                "symbol": symbol,
                "price": precio_actual,
                "tendencia_h1": format_trend(tendencia_h1),
                "tendencia_m15": format_trend(tendencia_m15),
                "ultimo_evento_m15": ultimo_evento_m15,
                "zona_madre_m15": {"desde": 0, "hasta": 0},
                "entrada": None,
                "stoploss": None,
                "tp_1_1": None,
                "score": 0,
                "ob": "NO",
                "fvg": "NO",
                "barrida": "NO",
                "estado": "SIN SETUP",
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            print_result_summary(result)
            return result
        
        # If zone exists, calculate full setup
        print(f"  OK ZONE created:")
        print(f"    - Desde: {zona['zona_desde']}")
        print(f"    - Hasta: {zona['zona_hasta']}")
        print(f"    - Direccion: {zona['direccion']}")
        
        # Extract zone components
        has_ob = zona.get('ob') is not None
        has_fvg = zona.get('fvg') is not None
        has_barrida = zona.get('barrida') is not None
        es_util = zona.get('es_util', False)
        
        print(f"    - OB: {'SI' if has_ob else 'NO'}")
        print(f"    - FVG: {'SI' if has_fvg else 'NO'}")
        print(f"    - Barrida: {'SI' if has_barrida else 'NO'}")
        
        # Get score from zone
        score = zona.get('score', 0)
        print(f"    - Score: {score}")
        print(f"    - es_util: {es_util} - {zona.get('motivo', 'N/A')}")
        
        # Get direccion_operativa
        direccion_operativa = zona.get('direccion_operativa', zona.get('direccion', 'ALCISTA'))
        
        # Calculate operational levels (entrada, stoploss, tp_1_1)
        niveles = calcular_niveles_operativos(zona, direccion_operativa)
        entrada = niveles["entrada"]
        stoploss = niveles["stoploss"]
        tp_1_1 = niveles["tp_1_1"]
        
        print(f"    - Entrada: {entrada}")
        print(f"    - StopLoss: {stoploss}")
        print(f"    - TP 1:1: {tp_1_1}")
        
        # Calculate dashboard state (velocidad M1 o posicion si no hay M1)
        estado_dashboard = calcular_estado_dashboard(
            precio_actual,
            entrada,
            zona['zona_desde'],
            zona['zona_hasta'],
            direccion_operativa,
            df_m1=df_m1,
            symbol=symbol
        )
        print(f"  Estado Dashboard (calculado): {estado_dashboard}")
        
        # Obtener estado previo guardado en Supabase (si existe)
        estado_previo = None
        existing_setup = None
        existe_setup_previo = False
        
        if supabase_service:
            existing_setup = supabase_service.get_active_setup(
                'SMC_M15_PRO',
                symbol,
                entrada,
                stoploss
            )
            if existing_setup:
                estado_previo = existing_setup.get('estado')
                existe_setup_previo = True
                print(f"  Estado Previo (guardado): {estado_previo}")
            else:
                print(f"  Estado Previo: NINGUNO (nueva zona)")
        else:
            print(f"  SUPABASE ERROR: Service not available, cannot read estado_previo")
        
        # Calculate historial state with state machine validation
        estado_historial, motivo_transicion = calcular_estado_historial(
            symbol,
            estado_dashboard,
            precio_actual,
            entrada,
            stoploss,
            tp_1_1,
            zona['zona_desde'],
            zona['zona_hasta'],
            estado_previo
        )
        print(f"  Estado Historial (validado): {estado_historial}")
        print(f"  Motivo transición: {motivo_transicion}")
        
        # Si la zona es invalida para el dashboard, tratarla como SIN SETUP
        if estado_historial == "SIN_SETUP":
            print(f"  WARNING: Zona invalida para dashboard ({symbol}) - precio fuera del rango valido")
            print(f"  entrada={entrada}, stoploss={stoploss}, precio={precio_actual}")
            print(f"  Retornando SIN SETUP para no mostrar zona invalida en dashboard")
            result = {
                "symbol": symbol,
                "price": precio_actual,
                "tendencia_h1": format_trend(tendencia_h1),
                "tendencia_m15": format_trend(tendencia_m15),
                "ultimo_evento_m15": ultimo_evento_m15,
                "zona_madre_m15": {"desde": 0, "hasta": 0},
                "entrada": None,
                "stoploss": None,
                "tp_1_1": None,
                "score": 0,
                "ob": "NO",
                "fvg": "NO",
                "barrida": "NO",
                "estado": "SIN SETUP",
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            print_result_summary(result)
            return result
        
        # LOG COMPLETO según requerimientos del problema
        print(f"\n=== LOG TRANSICION ESTADO {symbol} ===")
        print(f"  symbol: {symbol}")
        print(f"  existe_setup_previo: {existe_setup_previo}")
        print(f"  estado_previo: {estado_previo if estado_previo else 'NINGUNO'}")
        print(f"  estado_calculado: {estado_dashboard}")
        print(f"  estado_validado: {estado_historial}")
        print(f"  estado_final: {estado_historial}")
        print(f"  precio_actual: {precio_actual}")
        print(f"  zona_desde: {zona['zona_desde']}")
        print(f"  zona_hasta: {zona['zona_hasta']}")
        print(f"  entrada: {entrada}")
        print(f"  stoploss: {stoploss}")
        print(f"  tp_1_1: {tp_1_1}")
        print(f"  motivo_transicion: {motivo_transicion}")
        print(f"======================================\n")
        
        # COMPREHENSIVE LOG as requested in problem statement
        print(f"\n=== RESUMEN SETUP {symbol} ===")
        print(f"  zona_madre_m15: desde={zona['zona_desde']}, hasta={zona['zona_hasta']}")
        print(f"  score: {score}")
        print(f"  ob: {'SI' if has_ob else 'NO'}")
        print(f"  fvg: {'SI' if has_fvg else 'NO'}")
        print(f"  barrida: {'SI' if has_barrida else 'NO'}")
        print(f"  es_util: {es_util}")
        print(f"  estado_final: {estado_dashboard}")
        print(f"  guardado_historial: SI (zona valida con score={score})")
        print(f"===============================\n")
        
        # Build full response with zone
        # CRITICAL FIX: BUG 2 - Use estado_historial (validated) instead of estado_dashboard (raw)
        result = {
            "symbol": symbol,
            "price": precio_actual,
            "tendencia_h1": format_trend(tendencia_h1),
            "tendencia_m15": format_trend(tendencia_m15),
            "ultimo_evento_m15": ultimo_evento_m15,
            "zona_madre_m15": {
                "desde": float(zona.get('zona_desde', 0)),
                "hasta": float(zona.get('zona_hasta', 0))
            },
            "entrada": entrada,
            "stoploss": stoploss,
            "tp_1_1": tp_1_1,
            "estado_dashboard": estado_dashboard,  # Keep for debugging
            "estado_historial": estado_historial,  # Validated state
            "estado_final": estado_historial,      # NEW: Final state for dashboard
            "score": score,
            "ob": "SÍ" if has_ob else "NO",
            "fvg": "SÍ" if has_fvg else "NO",
            "barrida": "SÍ" if has_barrida else "NO",
            "estado": estado_historial,  # FIXED: Use estado_historial NOT estado_dashboard
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        print_result_summary(result)
        
        # Sync to Supabase (smart sync with debounce)
        sync_setup_to_supabase(result)
        
        return result
        
    except Exception as e:
        print(f"  ERROR analyzing {symbol}: {e}")
        import traceback
        traceback.print_exc()
        return create_sin_setup_response(symbol)


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
