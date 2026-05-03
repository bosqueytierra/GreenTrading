"""
SMC Engine - Lógica Smart Money Concepts.

Reorganización de la lógica existente en smc_m15_pro.py.
No contiene I/O (MT5, Supabase, UI). Solo cálculos puros sobre DataFrames.
"""

import pandas as pd


# =========================
# CONFIG
# =========================

SWING_LOOKBACK = 3
CLOSE_BREAK = True


# =========================
# SWINGS (helper interno)
# =========================

def detectar_swings(df, lookback=SWING_LOOKBACK):
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
# En el original, BOS y CHOCH se calculan en la misma pasada porque CHOCH
# depende del estado de tendencia previo. Mantenemos esa función núcleo
# intacta y exponemos detect_bos / detect_choch como filtros sobre su salida.

def _detect_structure(df, swings):
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
    """Devuelve solo los eventos BOS detectados sobre df."""
    if swings is None:
        swings = detectar_swings(df, SWING_LOOKBACK)
    eventos, _ = _detect_structure(df, swings)
    return [e for e in eventos if "BOS" in e["evento"]]


def detect_choch(df, swings=None):
    """Devuelve solo los eventos CHOCH detectados sobre df."""
    if swings is None:
        swings = detectar_swings(df, SWING_LOOKBACK)
    eventos, _ = _detect_structure(df, swings)
    return [e for e in eventos if "CHOCH" in e["evento"]]


# =========================
# FVG
# =========================

def detect_fvg(df):
    fvgs = []

    for i in range(2, len(df)):
        vela_1 = df.iloc[i-2]
        vela_3 = df.iloc[i]

        # FVG alcista: low actual > high de hace 2 velas
        if vela_3["low"] > vela_1["high"]:
            fvgs.append({
                "index": i,
                "time": df["time"].iloc[i],
                "tipo": "FVG_ALCISTA",
                "desde": float(vela_1["high"]),
                "hasta": float(vela_3["low"])
            })

        # FVG bajista: high actual < low de hace 2 velas
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
    idx = evento["index"]
    direccion = "ALCISTA" if "ALCISTA" in evento["evento"] else "BAJISTA"

    inicio = max(0, idx - 15)
    tramo = df.iloc[inicio:idx]

    if direccion == "ALCISTA":
        # última vela bajista antes del impulso
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
        # última vela alcista antes del impulso bajista
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
    """Devuelve el OB asociado a cada evento (mismo criterio que el original)."""
    obs = []
    for ev in eventos:
        ob = _buscar_order_block(df, ev)
        if ob is not None:
            obs.append(ob)
    return obs


# =========================
# BARRIDA / SWEEP (helper interno)
# =========================

def _detectar_barrida_previa(df, evento, direccion, lookback=30):
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
    """Construye la zona depurada M15 (equivalente a crear_zona_m15 del original)."""
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
    Placeholder: en smc_m15_pro.py no existe lógica de refinamiento M1.
    Para no crear lógica nueva, se devuelve la zona sin modificar.
    """
    return zona


# =========================
# ANALYZE SMC (función principal)
# =========================

def analyze_smc(df_h1, df_m15, df_m1=None):
    """
    Replica el cómputo del main() original (sin I/O, sin prints).
    Recibe DataFrames ya cargados y devuelve el resultado del análisis SMC.
    """
    swings_h1 = detectar_swings(df_h1, SWING_LOOKBACK)
    eventos_h1, tendencia_h1 = _detect_structure(df_h1, swings_h1)

    swings_m15 = detectar_swings(df_m15, SWING_LOOKBACK)
    eventos_m15, tendencia_m15 = _detect_structure(df_m15, swings_m15)

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
