"""
SMC Engine - Motor Smart Money Concepts completo.

Lógica extraída de smc_m15_pro.py.
No contiene I/O (MT5, Supabase, UI). Solo cálculos puros sobre DataFrames.

Funciones principales:
- detectar_swings: Detecta swing highs y lows
- detect_bos: Detecta Break of Structure
- detect_choch: Detecta Change of Character
- detect_fvg: Detecta Fair Value Gaps
- detect_order_blocks: Detecta Order Blocks
- detect_m15_zones: Crea zona depurada M15
- refine_zone_m1: Refinamiento M1 (passthrough)
- analyze_smc: Función principal de análisis
"""

import pandas as pd


# =========================
# CONFIGURACIÓN
# =========================

SWING_LOOKBACK = 3
CLOSE_BREAK = True


# =========================
# SWINGS
# =========================

def detectar_swings(df, lookback=SWING_LOOKBACK):
    """
    Detecta swing highs y swing lows en el DataFrame.
    
    Args:
        df: DataFrame con columnas ['high', 'low', 'time']
        lookback: Número de velas a considerar antes y después
    
    Returns:
        Lista de diccionarios con swings detectados
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
# ESTRUCTURA (BOS + CHOCH)
# =========================

def _detectar_estructura(df, swings):
    """
    Detecta estructura de mercado: BOS (Break of Structure) y CHOCH (Change of Character).
    Esta es la función interna que detecta ambos tipos de eventos en una sola pasada.
    
    Args:
        df: DataFrame con columnas ['close', 'high', 'low', 'time']
        swings: Lista de swings detectados
    
    Returns:
        Tupla (eventos, tendencia_actual)
    """
    eventos = []
    tendencia = None

    ultimo_high = None
    ultimo_low = None

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

        if rompe_high:
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

        elif rompe_low:
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

    return eventos, tendencia


def detect_bos(df, swings=None):
    """
    Detecta solo los eventos Break of Structure (BOS).
    
    Args:
        df: DataFrame con datos de velas
        swings: Lista de swings (opcional, se calculará si no se provee)
    
    Returns:
        Lista de eventos BOS
    """
    if swings is None:
        swings = detectar_swings(df, SWING_LOOKBACK)
    eventos, _ = _detectar_estructura(df, swings)
    return [e for e in eventos if "BOS" in e["evento"]]


def detect_choch(df, swings=None):
    """
    Detecta solo los eventos Change of Character (CHOCH).
    
    Args:
        df: DataFrame con datos de velas
        swings: Lista de swings (opcional, se calculará si no se provee)
    
    Returns:
        Lista de eventos CHOCH
    """
    if swings is None:
        swings = detectar_swings(df, SWING_LOOKBACK)
    eventos, _ = _detectar_estructura(df, swings)
    return [e for e in eventos if "CHOCH" in e["evento"]]


# =========================
# FVG (Fair Value Gaps)
# =========================

def detect_fvg(df):
    """
    Detecta Fair Value Gaps (FVG) - huecos dejados por movimientos impulsivos.
    
    FVG Alcista: low actual > high de hace 2 velas
    FVG Bajista: high actual < low de hace 2 velas
    
    Args:
        df: DataFrame con columnas ['high', 'low', 'time']
    
    Returns:
        Lista de FVGs detectados
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

def _buscar_order_block(df, evento):
    """
    Busca el Order Block asociado a un evento de estructura.
    
    Order Block Alcista: última vela bajista antes del impulso alcista
    Order Block Bajista: última vela alcista antes del impulso bajista
    
    Args:
        df: DataFrame con datos de velas
        evento: Diccionario con información del evento
    
    Returns:
        Diccionario con datos del Order Block o None
    """
    idx = evento["index"]
    direccion = "ALCISTA" if "ALCISTA" in evento["evento"] else "BAJISTA"

    inicio = max(0, idx - 15)
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


def detect_order_blocks(df, eventos):
    """
    Detecta Order Blocks para una lista de eventos.
    
    Args:
        df: DataFrame con datos de velas
        eventos: Lista de eventos de estructura
    
    Returns:
        Lista de Order Blocks detectados
    """
    obs = []
    for ev in eventos:
        ob = _buscar_order_block(df, ev)
        if ob is not None:
            obs.append(ob)
    return obs


# =========================
# BARRIDA / SWEEP
# =========================

def _detectar_barrida_previa(df, evento, direccion, lookback=30):
    """
    Detecta barridas de liquidez previas al evento.
    
    Barrida Alcista: vela que toca mínimo previo y cierra por encima
    Barrida Bajista: vela que toca máximo previo y cierra por debajo
    
    Args:
        df: DataFrame con datos de velas
        evento: Evento de estructura
        direccion: "ALCISTA" o "BAJISTA"
        lookback: Número de velas a revisar hacia atrás
    
    Returns:
        Diccionario con datos de barrida o None
    """
    idx = evento["index"]
    inicio = max(0, idx - lookback)
    tramo = df.iloc[inicio:idx]

    if len(tramo) < 5:
        return None

    if direccion == "ALCISTA":
        minimo_previo = tramo["low"].min()
        velas_barrida = tramo[
            (tramo["low"] < minimo_previo) &
            (tramo["close"] > minimo_previo)
        ]
    else:
        maximo_previo = tramo["high"].max()
        velas_barrida = tramo[
            (tramo["high"] > maximo_previo) &
            (tramo["close"] < maximo_previo)
        ]

    if velas_barrida.empty:
        return None

    v = velas_barrida.iloc[-1]

    return {
        "time": v["time"],
        "tipo": "BARRIDA_ALCISTA" if direccion == "ALCISTA" else "BARRIDA_BAJISTA",
        "high": float(v["high"]),
        "low": float(v["low"]),
        "close": float(v["close"])
    }


# =========================
# ZONA DEPURADA M15
# =========================

def detect_m15_zones(df_m15, eventos_m15, fvgs_m15):
    """
    Construye la zona depurada M15 combinando:
    - Último evento de estructura
    - Order Block
    - Fair Value Gap
    - Barrida previa
    
    Calcula un score de confluencia basado en los elementos presentes.
    
    Args:
        df_m15: DataFrame M15
        eventos_m15: Lista de eventos de estructura M15
        fvgs_m15: Lista de FVGs M15
    
    Returns:
        Diccionario con zona completa o None
    """
    if not eventos_m15:
        return None

    ultimo_evento = eventos_m15[-1]
    direccion = "ALCISTA" if "ALCISTA" in ultimo_evento["evento"] else "BAJISTA"

    ob = _buscar_order_block(df_m15, ultimo_evento)

    fvgs_validos = [
        f for f in fvgs_m15
        if f["index"] <= ultimo_evento["index"]
        and (
            (direccion == "ALCISTA" and f["tipo"] == "FVG_ALCISTA") or
            (direccion == "BAJISTA" and f["tipo"] == "FVG_BAJISTA")
        )
    ]

    fvg = fvgs_validos[-1] if fvgs_validos else None
    barrida = _detectar_barrida_previa(df_m15, ultimo_evento, direccion)

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
        return None

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

    return {
        "direccion": direccion,
        "evento": ultimo_evento,
        "ob": ob,
        "fvg": fvg,
        "barrida": barrida,
        "zona_desde": zona_desde,
        "zona_hasta": zona_hasta,
        "score": score
    }


# =========================
# REFINAMIENTO M1
# =========================

def refine_zone_m1(zona, df_m1=None):
    """
    Refinamiento de zona con timeframe M1.
    
    Nota: En smc_m15_pro.py no existe lógica de refinamiento M1.
    Esta función actúa como passthrough sin modificar la zona.
    
    Args:
        zona: Zona M15 a refinar
        df_m1: DataFrame M1 (opcional)
    
    Returns:
        Zona sin modificar
    """
    return zona


# =========================
# ANALYZE SMC (función principal)
# =========================

def analyze_smc(df_h1, df_m15, df_m1=None):
    """
    Función principal de análisis SMC.
    
    Procesa los DataFrames y ejecuta todo el análisis Smart Money Concepts:
    1. Detecta swings en H1 y M15
    2. Detecta estructura (BOS/CHOCH) en ambos timeframes
    3. Detecta FVGs en M15
    4. Construye zona depurada M15
    5. Opcionalmente refina con M1
    
    Args:
        df_h1: DataFrame con datos H1 (columnas: time, open, high, low, close)
        df_m15: DataFrame con datos M15 (columnas: time, open, high, low, close)
        df_m1: DataFrame con datos M1 (opcional)
    
    Returns:
        Diccionario con:
        - tendencia_h1: Tendencia actual en H1
        - tendencia_m15: Tendencia actual en M15
        - eventos_h1: Lista de eventos de estructura H1
        - eventos_m15: Lista de eventos de estructura M15
        - fvgs_m15: Lista de FVGs en M15
        - zona: Zona depurada M15 (o None)
        - precio_actual: Precio actual (close de última vela M15)
    """
    swings_h1 = detectar_swings(df_h1, SWING_LOOKBACK)
    eventos_h1, tendencia_h1 = _detectar_estructura(df_h1, swings_h1)

    swings_m15 = detectar_swings(df_m15, SWING_LOOKBACK)
    eventos_m15, tendencia_m15 = _detectar_estructura(df_m15, swings_m15)

    fvgs_m15 = detect_fvg(df_m15)

    zona = detect_m15_zones(df_m15, eventos_m15, fvgs_m15)

    if df_m1 is not None:
        zona = refine_zone_m1(zona, df_m1)

    precio_actual = float(df_m15["close"].iloc[-1]) if len(df_m15) else None

    return {
        "tendencia_h1": tendencia_h1,
        "tendencia_m15": tendencia_m15,
        "eventos_h1": eventos_h1,
        "eventos_m15": eventos_m15,
        "fvgs_m15": fvgs_m15,
        "zona": zona,
        "precio_actual": precio_actual,
    }
