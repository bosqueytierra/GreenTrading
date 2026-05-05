"""
SMC Engine TENDENCY H1 M15 - Motor Smart Money Concepts con validación simplificada.

Esta estrategia NUEVA valida SOLO:
1. Dirección del índice (Boom/Crash) + Tendencia H1 + Evento M15
2. NO valida tendencia M15 (solo informativa)

Diferencias con smc_engine_h1_m15.py:
- NO valida tendencia M15 (solo H1)
- Solo guarda zonas que cumplen validación (no hay DESCARTADA)
- Usa tabla independiente: smc_tendency_h1_m15_setups

Basado en smc_engine_h1_m15.py pero con lógica de validación diferente.
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


# =========================
# FVG (FAIR VALUE GAP)
# =========================

def detect_fvg(df):
    """
    Detecta Fair Value Gaps (FVG) en el DataFrame.
    
    FVG Alcista: GAP entre high[i-2] y low[i] (vela central no cubre gap)
    FVG Bajista: GAP entre low[i-2] y high[i] (vela central no cubre gap)
    
    Args:
        df: DataFrame con columnas ['high', 'low', 'time']
    
    Returns:
        Lista de diccionarios con FVGs detectados
    """
    fvgs = []

    for i in range(2, len(df)):
        high_2 = df["high"].iloc[i-2]
        low_2 = df["low"].iloc[i-2]
        high_1 = df["high"].iloc[i-1]
        low_1 = df["low"].iloc[i-1]
        high_0 = df["high"].iloc[i]
        low_0 = df["low"].iloc[i]

        # FVG Alcista
        if low_0 > high_2:
            fvgs.append({
                "time": df["time"].iloc[i],
                "index": i,
                "tipo": "FVG_ALCISTA",
                "desde": float(high_2),
                "hasta": float(low_0)
            })

        # FVG Bajista
        if high_0 < low_2:
            fvgs.append({
                "time": df["time"].iloc[i],
                "index": i,
                "tipo": "FVG_BAJISTA",
                "desde": float(low_2),
                "hasta": float(high_0)
            })

    return fvgs


# =========================
# ORDER BLOCKS
# =========================

def _buscar_order_block(df, evento, lookback=20):
    """
    Busca Order Block antes del evento de estructura.
    
    Order Block: Última vela opuesta antes de movimiento en dirección del evento.
    - OB Alcista: Última vela bajista antes de movimiento alcista
    - OB Bajista: Última vela alcista antes de movimiento bajista
    
    Args:
        df: DataFrame con datos de velas
        evento: Evento de estructura
        lookback: Número de velas a revisar hacia atrás
    
    Returns:
        Diccionario con datos del Order Block o None
    """
    idx = evento["index"]
    direccion = "ALCISTA" if "ALCISTA" in evento["evento"] else "BAJISTA"

    inicio = max(0, idx - lookback)
    tramo = df.iloc[inicio:idx]

    if len(tramo) < 2:
        return None

    if direccion == "ALCISTA":
        velas_bajistas = tramo[tramo["close"] < tramo["open"]]
        if velas_bajistas.empty:
            return None
        v = velas_bajistas.iloc[-1]
        return {
            "tipo": "OB_ALCISTA",
            "time": v["time"],
            "desde": float(v["low"]),
            "hasta": float(v["high"])
        }
    else:
        velas_alcistas = tramo[tramo["close"] > tramo["open"]]
        if velas_alcistas.empty:
            return None
        v = velas_alcistas.iloc[-1]
        return {
            "tipo": "OB_BAJISTA",
            "time": v["time"],
            "desde": float(v["low"]),
            "hasta": float(v["high"])
        }


# =========================
# BARRIDAS DE LIQUIDEZ
# =========================

def _detectar_barrida_previa(df, evento, direccion, lookback=40, initial_offset=5):
    """
    Detecta barridas de liquidez previas al evento.
    
    Barrida Alcista: vela que toca mínimo previo y cierra por encima
    Barrida Bajista: vela que toca máximo previo y cierra por debajo
    
    Args:
        df: DataFrame con datos de velas
        evento: Evento de estructura
        direccion: "ALCISTA" o "BAJISTA"
        lookback: Número de velas a revisar hacia atrás
        initial_offset: Offset inicial para evitar velas muy recientes
    
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
    
    Nota: En estrategia SMC_TENDENCY_H1_M15 no se usa refinamiento M1.
    Esta función actúa como passthrough sin modificar la zona.
    
    Args:
        zona: Zona M15 a refinar
        df_m1: DataFrame M1 (opcional)
    
    Returns:
        Zona sin modificar
    """
    return zona


# =========================
# VALIDACIÓN SMC_TENDENCY_H1_M15 (NUEVA ESTRATEGIA)
# =========================

def validar_smc_tendency_h1_m15(symbol, tendencia_h1, ultimo_evento_m15):
    """
    Valida que la dirección del índice + tendencia H1 + evento M15 estén alineados.
    
    REGLA ABSOLUTA para SMC_TENDENCY_H1_M15:
    - BOOM: H1 ALCISTA + (CHOCH_ALCISTA o BOS_ALCISTA)
    - CRASH: H1 BAJISTA + (CHOCH_BAJISTA o BOS_BAJISTA)
    
    IMPORTANTE: NO valida tendencia M15 (solo informativa)
    
    Args:
        symbol: Símbolo del índice (ej: "Boom 1000 Index", "Crash 900 Index")
        tendencia_h1: Tendencia actual en H1 ("ALCISTA" o "BAJISTA")
        ultimo_evento_m15: Diccionario con último evento M15 (debe tener key "evento")
    
    Returns:
        Tupla (es_valido: bool, razon: str)
    """
    # Determinar tipo de índice
    tipo_indice = "BOOM" if "Boom" in symbol else "CRASH" if "Crash" in symbol else None
    
    if not tipo_indice:
        return False, "Símbolo no reconocido como Boom o Crash"
    
    if not tendencia_h1:
        return False, "Tendencia H1 no definida"
    
    if not ultimo_evento_m15:
        return False, "No hay evento M15"
    
    evento_m15 = ultimo_evento_m15.get("evento", "")
    
    # Validación para BOOM
    if tipo_indice == "BOOM":
        if tendencia_h1 != "ALCISTA":
            return False, f"BOOM requiere H1 ALCISTA (actual: {tendencia_h1})"
        
        if "CHOCH_ALCISTA" in evento_m15 or "BOS_ALCISTA" in evento_m15:
            return True, "✅ VÁLIDO: BOOM + H1 ALCISTA + Evento M15 ALCISTA"
        else:
            return False, f"BOOM requiere evento M15 alcista (actual: {evento_m15})"
    
    # Validación para CRASH
    elif tipo_indice == "CRASH":
        if tendencia_h1 != "BAJISTA":
            return False, f"CRASH requiere H1 BAJISTA (actual: {tendencia_h1})"
        
        if "CHOCH_BAJISTA" in evento_m15 or "BOS_BAJISTA" in evento_m15:
            return True, "✅ VÁLIDO: CRASH + H1 BAJISTA + Evento M15 BAJISTA"
        else:
            return False, f"CRASH requiere evento M15 bajista (actual: {evento_m15})"
    
    return False, "Condición no reconocida"


# =========================
# ANALYZE SMC TENDENCY H1 M15
# =========================

def analyze_smc_tendency_h1_m15(symbol, df_h1, df_m15, df_m1=None):
    """
    Función principal de análisis SMC_TENDENCY_H1_M15.
    
    Procesa los DataFrames y ejecuta análisis Smart Money Concepts con validación simplificada:
    1. Detecta swings en H1 y M15
    2. Detecta estructura (BOS/CHOCH) en ambos timeframes
    3. Detecta FVGs en M15
    4. Construye zona depurada M15
    5. VALIDA SOLO: Dirección índice + H1 + Evento M15 (NO valida tendencia M15)
    6. Si no cumple validación, retorna zona como NO válida (no se guardará)
    
    Args:
        symbol: Símbolo del índice
        df_h1: DataFrame con datos H1 (columnas: time, open, high, low, close)
        df_m15: DataFrame con datos M15 (columnas: time, open, high, low, close)
        df_m1: DataFrame con datos M1 (opcional)
    
    Returns:
        Diccionario con:
        - tendencia_h1: Tendencia actual en H1
        - tendencia_m15: Tendencia actual en M15 (informativa, NO se usa para validar)
        - eventos_h1: Lista de eventos de estructura H1
        - eventos_m15: Lista de eventos de estructura M15
        - fvgs_m15: Lista de FVGs en M15
        - zona: Zona depurada M15 (o None)
        - precio_actual: Precio actual (close de última vela M15)
        - es_valido: True si cumple validación (índice + H1 + evento M15), False si no
        - razon_validacion: Mensaje explicativo de validación
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

    # NUEVA VALIDACIÓN SMC_TENDENCY_H1_M15
    # Solo valida: Dirección índice + Tendencia H1 + Evento M15
    # NO valida tendencia M15 (solo informativa)
    es_valido = False
    razon_validacion = "No se pudo validar"
    
    if zona and eventos_m15:
        ultimo_evento_m15 = eventos_m15[-1]
        es_valido, razon_validacion = validar_smc_tendency_h1_m15(symbol, tendencia_h1, ultimo_evento_m15)
    elif not zona:
        razon_validacion = "No hay zona M15 detectada"
    elif not eventos_m15:
        razon_validacion = "No hay eventos M15"

    return {
        "tendencia_h1": tendencia_h1,
        "tendencia_m15": tendencia_m15,  # Informativa, NO se usa para validar
        "eventos_h1": eventos_h1,
        "eventos_m15": eventos_m15,
        "fvgs_m15": fvgs_m15,
        "zona": zona,
        "precio_actual": precio_actual,
        "es_valido": es_valido,
        "razon_validacion": razon_validacion,
    }
