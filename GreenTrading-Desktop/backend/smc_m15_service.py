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

# Configuration
SWING_LOOKBACK = 3
CLOSE_BREAK = True
M1_VELAS_ZONA = 15


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

        if es_util:
            return zona

    return None


# =========================
# MAIN ANALYSIS FUNCTION
# =========================

def analyze_symbol_smc(symbol: str, df_h1: pd.DataFrame, df_m15: pd.DataFrame) -> dict:
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
        # NIVEL B: SETUP/ZONA (OPCIONAL)
        # ===================================================================
        print(f"  Attempting zone creation...")
        
        # Detect FVGs
        fvgs_m15 = detectar_fvg(df_m15)
        print(f"    - FVGs M15: {len(fvgs_m15)}")
        
        # Try to create zone
        zona = crear_zona_m15(df_m15, eventos_m15, fvgs_m15, symbol, precio_actual)
        
        # If NO zone, return BASE STRUCTURE with SIN SETUP for zone part
        if not zona:
            print(f"  WARNING NO ZONE created (no OB/FVG or not operative)")
            print(f"  Returning BASE STRUCTURE with SIN SETUP")
            result = {
                "symbol": symbol,
                "price": precio_actual,
                "tendencia_h1": format_trend(tendencia_h1),
                "tendencia_m15": format_trend(tendencia_m15),
                "ultimo_evento_m15": ultimo_evento_m15,
                "zona_madre_m15": {"desde": 0, "hasta": 0},
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
        
        print(f"    - OB: {'SI' if has_ob else 'NO'}")
        print(f"    - FVG: {'SI' if has_fvg else 'NO'}")
        print(f"    - Barrida: {'SI' if has_barrida else 'NO'}")
        
        # Get score from zone
        score = zona.get('score', 0)
        print(f"    - Score: {score}")
        
        # Determine state
        estado = "ACTIVA" if score > 0 else "SIN SETUP"
        print(f"  Estado: {estado}")
        
        # Build full response with zone
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
            "score": score,
            "ob": "SÍ" if has_ob else "NO",
            "fvg": "SÍ" if has_fvg else "NO",
            "barrida": "SÍ" if has_barrida else "NO",
            "estado": estado,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        print_result_summary(result)
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
