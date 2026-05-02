import MetaTrader5 as mt5
import pandas as pd

# =========================
# CONFIG
# =========================

SYMBOL = "Boom 1000 Index"

TIMEFRAME_DIRECCION = mt5.TIMEFRAME_H1
TIMEFRAME_ZONA = mt5.TIMEFRAME_M15

VELAS_H1 = 500
VELAS_M15 = 800

SWING_LOOKBACK = 3
CLOSE_BREAK = True


# =========================
# DATA
# =========================

def get_data(symbol, timeframe, candles):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, candles)

    if rates is None:
        return pd.DataFrame()

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df


# =========================
# SWINGS
# =========================

def detectar_swings(df, lookback=3):
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
# BOS / CHOCH SIMPLE
# =========================

def detectar_estructura(df, swings):
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
# FVG
# =========================

def detectar_fvg(df):
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
# ORDER BLOCK SIMPLE
# =========================

def buscar_order_block(df, evento):
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


# =========================
# SWEEP / BARRIDA SIMPLE
# =========================

def detectar_barrida_previa(df, evento, direccion, lookback=30):
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

def crear_zona_m15(df_m15, eventos_m15, fvgs_m15):
    if not eventos_m15:
        return None

    ultimo_evento = eventos_m15[-1]
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
# MAIN
# =========================

def main():
    if not mt5.initialize():
        print("No se pudo conectar a MT5 ❌")
        print(mt5.last_error())
        return

    mt5.symbol_select(SYMBOL, True)

    df_h1 = get_data(SYMBOL, TIMEFRAME_DIRECCION, VELAS_H1)
    df_m15 = get_data(SYMBOL, TIMEFRAME_ZONA, VELAS_M15)

    if df_h1.empty or df_m15.empty:
        print("No se pudo obtener data.")
        mt5.shutdown()
        return

    swings_h1 = detectar_swings(df_h1, SWING_LOOKBACK)
    eventos_h1, tendencia_h1 = detectar_estructura(df_h1, swings_h1)

    swings_m15 = detectar_swings(df_m15, SWING_LOOKBACK)
    eventos_m15, tendencia_m15 = detectar_estructura(df_m15, swings_m15)

    fvgs_m15 = detectar_fvg(df_m15)

    zona = crear_zona_m15(df_m15, eventos_m15, fvgs_m15)

    precio_actual = float(df_m15["close"].iloc[-1])

    print("\n==============================")
    print(" FELIPITO TRADING - SMC M15 PRO")
    print("==============================")
    print(f"Índice: {SYMBOL}")
    print(f"Precio actual: {round(precio_actual, 3)}")
    print("------------------------------")
    print(f"Tendencia H1: {tendencia_h1}")
    print(f"Tendencia M15: {tendencia_m15}")

    if eventos_h1:
        print(f"Último evento H1: {eventos_h1[-1]['evento']} | nivel: {round(eventos_h1[-1]['nivel_roto'], 3)}")

    if eventos_m15:
        print(f"Último evento M15: {eventos_m15[-1]['evento']} | nivel: {round(eventos_m15[-1]['nivel_roto'], 3)}")

    print("------------------------------")

    if not zona:
        print("No hay zona M15 depurada por ahora.")
    else:
        print("ZONA DEPURADA M15:")
        print(f"Dirección: {zona['direccion']}")
        print(f"Desde: {round(zona['zona_desde'], 3)}")
        print(f"Hasta: {round(zona['zona_hasta'], 3)}")
        print(f"Score: {zona['score']} / 10 aprox.")

        if zona["ob"]:
            print(f"OB: {zona['ob']['tipo']} | {round(zona['ob']['desde'],3)} - {round(zona['ob']['hasta'],3)}")

        if zona["fvg"]:
            print(f"FVG: {zona['fvg']['tipo']} | {round(zona['fvg']['desde'],3)} - {round(zona['fvg']['hasta'],3)}")

        if zona["barrida"]:
            print(f"Barrida previa: SÍ | {zona['barrida']['time']}")
        else:
            print("Barrida previa: NO detectada")

        if zona["zona_desde"] <= precio_actual <= zona["zona_hasta"]:
            print("ESTADO: PRECIO DENTRO DE ZONA ⚠️")
        else:
            distancia = min(
                abs(precio_actual - zona["zona_desde"]),
                abs(precio_actual - zona["zona_hasta"])
            )
            print(f"ESTADO: Precio fuera de zona | distancia aprox: {round(distancia, 3)}")

    mt5.shutdown()


if __name__ == "__main__":
    main()