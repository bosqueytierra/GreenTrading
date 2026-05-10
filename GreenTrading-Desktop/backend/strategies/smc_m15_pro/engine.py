#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SMC M15 PRO strategy engine (FASE 2A).

Contains only pure SMC analysis helpers moved/copied from smc_m15_service.py.
No tracking mode, Supabase sync, endpoint logic, or state machine orchestration.
"""

from strategies.base_strategy import BaseStrategy


SWING_LOOKBACK = 3
CLOSE_BREAK = True


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

        prev_highs = df["high"].iloc[i - lookback:i]
        next_highs = df["high"].iloc[i + 1:i + 1 + lookback]

        prev_lows = df["low"].iloc[i - lookback:i]
        next_lows = df["low"].iloc[i + 1:i + 1 + lookback]

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
        vela_1 = df.iloc[i - 2]
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


def format_trend(trend: str) -> str:
    """Format trend name."""
    if trend is None:
        return "--"
    return trend.upper()


def get_last_event(eventos: list) -> str:
    """
    Get last M15 event (BOS or CHOCH).

    Args:
        eventos: List of structure events

    Returns:
        Event string (BOS_ALCISTA, CHOCH_BAJISTA, etc.)
    """
    if not eventos:
        return "--"

    # Get last event
    last = eventos[-1]

    # Events have 'evento' field: BOS_ALCISTA, CHOCH_BAJISTA, etc.
    evento = last.get('evento', '')

    if evento:
        return evento.upper()

    return "--"


class SMCM15ProEngine(BaseStrategy):
    """
    Strategy object placeholder for the new multi-strategy architecture.

    FASE 2A only exposes pure analysis helpers; full analyze flow remains in
    smc_m15_service.py and will be moved in FASE 2B.
    """

    strategy_id = "SMC_M15_PRO"
    strategy_name = "SMC M15 PRO"

    def analyze(self, symbol, df_h1, df_m15, df_m1=None, **kwargs):
        raise NotImplementedError(
            "SMCM15ProEngine.analyze() will be integrated in FASE 2B. "
            "Use smc_m15_service.analyze_symbol_smc() during FASE 2A."
        )
