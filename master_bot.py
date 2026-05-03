import tkinter as tk
from tkinter import ttk
import MetaTrader5 as mt5
import pandas as pd
import os
import requests
from dotenv import load_dotenv

# =========================
# CONFIG
# =========================

load_dotenv()

APP_NAME = "GreenTrading"
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

indices = [
    "Boom 1000 Index",
    "Boom 900 Index",
    "Boom 600 Index",
    "Boom 500 Index",
    "Boom 300 Index",
    "Crash 1000 Index",
    "Crash 900 Index",
    "Crash 600 Index",
    "Crash 500 Index",
    "Crash 300 Index",
]

timeframes = {
    "M1": mt5.TIMEFRAME_M1,
    "M15": mt5.TIMEFRAME_M15,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
}

SWING_LOOKBACK = 3
CLOSE_BREAK = True
M1_VELAS_ZONA = 15


# =========================
# SUPABASE
# =========================

def supabase_headers():
    return {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }


def guardar_en_supabase(data):
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return False, "Faltan SUPABASE_URL o SUPABASE_ANON_KEY en .env"

    url = f"{SUPABASE_URL}/rest/v1/analisis_zonas"

    try:
        response = requests.post(url, headers=supabase_headers(), json=data, timeout=15)

        if response.status_code in [200, 201]:
            return True, "Guardado en Supabase ✅"

        return False, f"Error Supabase {response.status_code}: {response.text}"

    except Exception as e:
        return False, f"Error conectando a Supabase: {e}"


def obtener_historial(limit=50):
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return []

    url = (
        f"{SUPABASE_URL}/rest/v1/analisis_zonas"
        f"?select=*&order=fecha_analisis.desc&limit={limit}"
    )

    try:
        response = requests.get(url, headers=supabase_headers(), timeout=15)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass

    return []


# =========================
# DATA MT5
# =========================

def get_candles(symbol, timeframe, days):
    candles_per_day = {
        "M1": 1440,
        "M15": 96,
        "H1": 24,
        "H4": 6,
    }

    n = candles_per_day[timeframe] * int(days)
    rates = mt5.copy_rates_from_pos(symbol, timeframes[timeframe], 0, n)

    if rates is None:
        return pd.DataFrame()

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df


def get_candles_direct(symbol, timeframe_mt5, candles):
    rates = mt5.copy_rates_from_pos(symbol, timeframe_mt5, 0, candles)

    if rates is None:
        return pd.DataFrame()

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df


# =========================
# FILTRO BOOM / CRASH
# =========================

def tipo_indice(symbol):
    if "Boom" in symbol:
        return "BOOM"
    if "Crash" in symbol:
        return "CRASH"
    return "NO_RECONOCIDO"


def direccion_operativa_por_indice(symbol):
    if "Boom" in symbol:
        return "ALCISTA"
    if "Crash" in symbol:
        return "BAJISTA"
    return None


def validar_zona_operativa(symbol, zona, precio_actual):
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
# ZONAS BÁSICAS
# =========================

def detectar_zonas(df):
    zonas = []

    for i in range(2, len(df) - 2):
        high = df["high"].iloc[i]
        low = df["low"].iloc[i]

        if high > df["high"].iloc[i - 1] and high > df["high"].iloc[i + 1]:
            zonas.append(high)

        if low < df["low"].iloc[i - 1] and low < df["low"].iloc[i + 1]:
            zonas.append(low)

    return zonas


def agrupar(zonas, tol=10):
    grupos = []

    for z in zonas:
        found = False

        for g in grupos:
            if abs(g["precio"] - z) < tol:
                g["conteo"] += 1
                g["precio"] = (g["precio"] + z) / 2
                found = True
                break

        if not found:
            grupos.append({"precio": z, "conteo": 1})

    return grupos


# =========================
# SMC
# =========================

def detectar_swings(df, lookback=3):
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
# ZONA M15 + ZONA FINA M1
# =========================

def crear_zona_m15(df_m15, eventos_m15, fvgs_m15, symbol, precio_actual):
    if not eventos_m15:
        return None

    direccion_operativa = direccion_operativa_por_indice(symbol)
    eventos_filtrados = []

    for evento in eventos_m15:
        direccion_evento = "ALCISTA" if "ALCISTA" in evento["evento"] else "BAJISTA"
        if direccion_operativa and direccion_evento != direccion_operativa:
            continue
        eventos_filtrados.append(evento)

    if not eventos_filtrados:
        return None

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


def crear_zona_fina_m1(df_m1, zona_m15, symbol, velas_usadas=15):
    if df_m1.empty or not zona_m15:
        return None

    precio_actual = float(df_m1["close"].iloc[-1])
    direccion = direccion_operativa_por_indice(symbol)

    cercanas = df_m1[
        (df_m1["high"] >= zona_m15["zona_desde"]) &
        (df_m1["low"] <= zona_m15["zona_hasta"])
    ]

    if not cercanas.empty:
        idx = cercanas.index[-1]
        inicio = max(0, idx - velas_usadas + 1)
        tramo = df_m1.iloc[inicio:idx + 1]
        confirmacion = "M1 dentro/cerca de zona madre M15"
    else:
        tramo = df_m1.tail(velas_usadas)
        confirmacion = "M1 últimas velas cercanas al precio actual"

    if tramo.empty:
        return None

    if direccion == "ALCISTA":
        zona_desde = float(tramo["low"].min())
        zona_hasta = float(tramo["close"].median())
    elif direccion == "BAJISTA":
        zona_desde = float(tramo["close"].median())
        zona_hasta = float(tramo["high"].max())
    else:
        zona_desde = float(tramo["low"].min())
        zona_hasta = float(tramo["high"].max())

    if zona_desde > zona_hasta:
        zona_desde, zona_hasta = zona_hasta, zona_desde

    dentro = zona_desde <= precio_actual <= zona_hasta

    return {
        "zona_m1_desde": zona_desde,
        "zona_m1_hasta": zona_hasta,
        "m1_confirmacion": confirmacion,
        "velas_m1_usadas": velas_usadas,
        "precio_dentro_m1": dentro
    }


def estado_inicial_zona(zona, precio_actual):
    if zona["zona_desde"] <= precio_actual <= zona["zona_hasta"]:
        return "PRECIO_DENTRO_DE_ZONA"
    return "PRECIO_FUERA_DE_ZONA"


# =========================
# ANÁLISIS
# =========================

def analizar_smc_pro(symbol):
    df_h1 = get_candles_direct(symbol, mt5.TIMEFRAME_H1, 500)
    df_m15 = get_candles_direct(symbol, mt5.TIMEFRAME_M15, 800)
    df_m1 = get_candles_direct(symbol, mt5.TIMEFRAME_M1, 600)

    if df_h1.empty or df_m15.empty:
        return "No se pudo obtener data H1/M15.\n"

    # Excluir la última vela (abierta) de cada timeframe para comparar solo velas cerradas
    df_h1 = df_h1.iloc[:-1]
    df_m15 = df_m15.iloc[:-1]
    df_m1 = df_m1.iloc[:-1]

    swings_h1 = detectar_swings(df_h1, SWING_LOOKBACK)
    eventos_h1, tendencia_h1 = detectar_estructura(df_h1, swings_h1)

    swings_m15 = detectar_swings(df_m15, SWING_LOOKBACK)
    eventos_m15, tendencia_m15 = detectar_estructura(df_m15, swings_m15)

    fvgs_m15 = detectar_fvg(df_m15)

    precio_actual = float(df_m15["close"].iloc[-1])
    zona = crear_zona_m15(df_m15, eventos_m15, fvgs_m15, symbol, precio_actual)
    zona_m1 = crear_zona_fina_m1(df_m1, zona, symbol, M1_VELAS_ZONA)

    direccion_operativa = direccion_operativa_por_indice(symbol)

    resultado = ""
    resultado += "GREEN TRADING - SMC M15 PRO\n"
    resultado += "========================================\n"
    resultado += f"Índice: {symbol}\n"
    resultado += f"Precio actual: {round(precio_actual, 3)}\n"
    resultado += "----------------------------------------\n"

    if direccion_operativa == "ALCISTA":
        resultado += "Tipo índice: BOOM\n"
        resultado += "Sesgo buscado: REACCIÓN ALCISTA\n"
        resultado += "Filtro: zona madre bajo el precio actual\n"
    elif direccion_operativa == "BAJISTA":
        resultado += "Tipo índice: CRASH\n"
        resultado += "Sesgo buscado: REACCIÓN BAJISTA\n"
        resultado += "Filtro: zona madre sobre el precio actual\n"

    resultado += "----------------------------------------\n"
    resultado += f"Tendencia H1: {tendencia_h1}\n"
    resultado += f"Tendencia M15: {tendencia_m15}\n"

    if eventos_h1:
        resultado += f"Último evento H1: {eventos_h1[-1]['evento']} | nivel: {round(eventos_h1[-1]['nivel_roto'], 3)}\n"

    if eventos_m15:
        resultado += f"Último evento M15: {eventos_m15[-1]['evento']} | nivel: {round(eventos_m15[-1]['nivel_roto'], 3)}\n"

    resultado += "----------------------------------------\n"

    if not zona:
        resultado += "No hay zona M15 depurada por ahora.\n"
        return resultado

    estado = estado_inicial_zona(zona, precio_actual)

    data_supabase = {
        "indice": symbol,
        "tipo_indice": tipo_indice(symbol),
        "precio_actual": precio_actual,
        "direccion_buscada": zona["direccion"],
        "temporalidad": "M15",
        "zona_desde": zona["zona_desde"],
        "zona_hasta": zona["zona_hasta"],
        "score": int(zona["score"]),
        "evento": zona["evento"]["evento"],
        "ob": zona["ob"] is not None,
        "fvg": zona["fvg"] is not None,
        "barrida": zona["barrida"] is not None,
        "zona_util": bool(zona["es_util"]),
        "estado_inicial": estado,
        "comentario": "Guardado automático desde GreenTrading"
    }

    if zona_m1:
        data_supabase["zona_m1_desde"] = zona_m1["zona_m1_desde"]
        data_supabase["zona_m1_hasta"] = zona_m1["zona_m1_hasta"]
        data_supabase["m1_confirmacion"] = zona_m1["m1_confirmacion"]
        data_supabase["velas_m1_usadas"] = zona_m1["velas_m1_usadas"]

    guardado_ok, mensaje_guardado = guardar_en_supabase(data_supabase)

    resultado += "ZONA MADRE M15\n"
    resultado += f"Dirección: {zona['direccion']}\n"
    resultado += f"Desde: {round(zona['zona_desde'], 3)}\n"
    resultado += f"Hasta: {round(zona['zona_hasta'], 3)}\n"
    resultado += f"Score: {zona['score']} / 12 aprox.\n"
    resultado += f"Zona útil: {'SÍ' if zona['es_util'] else 'NO'}\n"
    resultado += f"Motivo: {zona['motivo']}\n"

    if zona["ob"]:
        resultado += f"OB: {zona['ob']['tipo']} | {round(zona['ob']['desde'], 3)} - {round(zona['ob']['hasta'], 3)}\n"

    if zona["fvg"]:
        resultado += f"FVG: {zona['fvg']['tipo']} | {round(zona['fvg']['desde'], 3)} - {round(zona['fvg']['hasta'], 3)}\n"

    resultado += f"Barrida previa: {'SÍ' if zona['barrida'] else 'NO'}\n"
    resultado += f"Estado M15: {estado}\n"
    resultado += "----------------------------------------\n"

    if zona_m1:
        resultado += "ZONA FINA M1\n"
        resultado += f"Desde: {round(zona_m1['zona_m1_desde'], 3)}\n"
        resultado += f"Hasta: {round(zona_m1['zona_m1_hasta'], 3)}\n"
        resultado += f"Velas usadas: {zona_m1['velas_m1_usadas']}\n"
        resultado += f"Confirmación: {zona_m1['m1_confirmacion']}\n"
        resultado += f"Precio dentro M1: {'SÍ' if zona_m1['precio_dentro_m1'] else 'NO'}\n"
    else:
        resultado += "No se pudo crear zona fina M1.\n"

    resultado += "----------------------------------------\n"
    resultado += f"SUPABASE: {mensaje_guardado}\n"

    return resultado


# =========================
# ACCIONES UI
# =========================

def analizar():
    symbol = combo_indice.get()
    modo = combo_modo.get()

    output.delete("1.0", tk.END)
    output.insert(tk.END, "Analizando mercado...\n")

    if not mt5.initialize():
        output.delete("1.0", tk.END)
        output.insert(tk.END, "No se pudo conectar a MT5\n")
        output.insert(tk.END, str(mt5.last_error()))
        return

    mt5.symbol_select(symbol, True)

    if modo == "SMC M15 Pro":
        resultado = analizar_smc_pro(symbol)
        mt5.shutdown()
        output.delete("1.0", tk.END)
        output.insert(tk.END, resultado)
        cargar_historial()
        return

    resultado = f"{APP_NAME}\n"
    resultado += f"Índice seleccionado: {symbol}\n"
    resultado += "Modo: Zonas Básicas\n"
    resultado += "----------------------------------------\n"

    zonas_por_tf = {}

    for tf, var in tf_vars.items():
        if var.get():
            try:
                dias = int(entries[tf].get())
            except ValueError:
                resultado += f"\nError: días inválidos en {tf}\n"
                continue

            df = get_candles(symbol, tf, dias)

            if df.empty:
                resultado += f"\nNo se pudo obtener data para {tf}\n"
                continue

            zonas = detectar_zonas(df)
            grupos = agrupar(zonas)

            fuertes = [g for g in grupos if g["conteo"] >= 5]
            zonas_por_tf[tf] = fuertes

            resultado += f"\nZONAS FUERTES {tf} ({dias} días):\n"

            if not fuertes:
                resultado += "Sin zonas fuertes detectadas.\n"

            for z in fuertes:
                resultado += f"Precio: {round(float(z['precio']), 2)} | fuerza: {z['conteo']}\n"

    mt5.shutdown()
    output.delete("1.0", tk.END)
    output.insert(tk.END, resultado)


def cargar_historial():
    historial_box.delete("1.0", tk.END)
    rows = obtener_historial(40)

    if not rows:
        historial_box.insert(tk.END, "Sin historial o no se pudo conectar a Supabase.\n")
        return

    for r in rows:
        historial_box.insert(tk.END, "----------------------------------------\n")
        historial_box.insert(tk.END, f"Fecha: {r.get('fecha_analisis')}\n")
        historial_box.insert(tk.END, f"Índice: {r.get('indice')} | {r.get('tipo_indice')}\n")
        historial_box.insert(tk.END, f"Precio: {r.get('precio_actual')}\n")
        historial_box.insert(tk.END, f"Zona M15: {r.get('zona_desde')} - {r.get('zona_hasta')}\n")
        historial_box.insert(tk.END, f"Zona M1: {r.get('zona_m1_desde')} - {r.get('zona_m1_hasta')}\n")
        historial_box.insert(tk.END, f"Score: {r.get('score')} | Evento: {r.get('evento')}\n")
        historial_box.insert(tk.END, f"OB: {r.get('ob')} | FVG: {r.get('fvg')} | Barrida: {r.get('barrida')}\n")
        historial_box.insert(tk.END, f"Útil: {r.get('zona_util')} | Estado: {r.get('estado_inicial')}\n")


def cargar_estadisticas():
    stats_box.delete("1.0", tk.END)
    rows = obtener_historial(200)

    if not rows:
        stats_box.insert(tk.END, "Sin datos para estadísticas.\n")
        return

    df = pd.DataFrame(rows)

    stats_box.insert(tk.END, "GREEN TRADING - ESTADÍSTICAS BÁSICAS\n")
    stats_box.insert(tk.END, "========================================\n")
    stats_box.insert(tk.END, f"Total análisis guardados: {len(df)}\n\n")

    if "tipo_indice" in df:
        stats_box.insert(tk.END, "Por tipo de índice:\n")
        stats_box.insert(tk.END, str(df["tipo_indice"].value_counts()))
        stats_box.insert(tk.END, "\n\n")

    if "evento" in df:
        stats_box.insert(tk.END, "Por evento:\n")
        stats_box.insert(tk.END, str(df["evento"].value_counts()))
        stats_box.insert(tk.END, "\n\n")

    if "score" in df:
        stats_box.insert(tk.END, "Score promedio:\n")
        stats_box.insert(tk.END, str(round(pd.to_numeric(df["score"], errors="coerce").mean(), 2)))
        stats_box.insert(tk.END, "\n")


# =========================
# UI GREEN TRADING
# =========================

root = tk.Tk()
root.title(APP_NAME)
root.geometry("1360x820")
root.minsize(1200, 740)
root.configure(bg="#0f0f0f")

style = ttk.Style()
style.theme_use("clam")

style.configure(
    "TNotebook",
    background="#0f0f0f",
    borderwidth=0
)

style.configure(
    "TNotebook.Tab",
    background="#1a1a1a",
    foreground="#d8d8d8",
    padding=(18, 10),
    font=("Segoe UI", 10, "bold")
)

style.map(
    "TNotebook.Tab",
    background=[("selected", "#f2f2f2")],
    foreground=[("selected", "#111111")]
)

style.configure(
    "TCombobox",
    fieldbackground="#191919",
    background="#191919",
    foreground="white",
    arrowcolor="white",
    padding=8
)

# HEADER
topbar = tk.Frame(root, bg="#111111", height=76)
topbar.pack(fill="x")

logo = tk.Label(
    topbar,
    text="$",
    font=("Segoe UI", 30, "bold"),
    bg="#111111",
    fg="#f2f2f2",
    width=3
)
logo.pack(side="left", padx=(24, 8))

title_frame = tk.Frame(topbar, bg="#111111")
title_frame.pack(side="left", pady=12)

tk.Label(
    title_frame,
    text="GreenTrading",
    font=("Segoe UI", 22, "bold"),
    bg="#111111",
    fg="white"
).pack(anchor="w")

tk.Label(
    title_frame,
    text="SMC · Zonas · Backtesting vivo · Supabase",
    font=("Segoe UI", 10),
    bg="#111111",
    fg="#9a9a9a"
).pack(anchor="w")

status_label = tk.Label(
    topbar,
    text="MT5 + Supabase",
    font=("Segoe UI", 10, "bold"),
    bg="#111111",
    fg="#cfcfcf"
)
status_label.pack(side="right", padx=28)

# BODY
body = tk.Frame(root, bg="#0f0f0f")
body.pack(fill="both", expand=True, padx=22, pady=18)

notebook = ttk.Notebook(body)
notebook.pack(fill="both", expand=True)

tab_analisis = tk.Frame(notebook, bg="#0f0f0f")
tab_historial = tk.Frame(notebook, bg="#0f0f0f")
tab_stats = tk.Frame(notebook, bg="#0f0f0f")

notebook.add(tab_analisis, text="Análisis en vivo")
notebook.add(tab_historial, text="Historial")
notebook.add(tab_stats, text="Estadísticas")

# ANALISIS TAB
left_panel = tk.Frame(tab_analisis, bg="#151515", width=380)
left_panel.pack(side="left", fill="y", padx=(0, 18), pady=18)
left_panel.pack_propagate(False)

right_panel = tk.Frame(tab_analisis, bg="#0f0f0f")
right_panel.pack(side="left", fill="both", expand=True, pady=18)

tk.Label(
    left_panel,
    text="Configuración",
    font=("Segoe UI", 18, "bold"),
    bg="#151515",
    fg="white"
).pack(anchor="w", padx=20, pady=(20, 12))

tk.Label(
    left_panel,
    text="Índice",
    font=("Segoe UI", 10, "bold"),
    bg="#151515",
    fg="#d8d8d8"
).pack(anchor="w", padx=20)

combo_indice = ttk.Combobox(left_panel, values=indices, font=("Segoe UI", 11))
combo_indice.set(indices[0])
combo_indice.pack(fill="x", padx=20, pady=(6, 18), ipady=7)

tk.Label(
    left_panel,
    text="Modo de análisis",
    font=("Segoe UI", 10, "bold"),
    bg="#151515",
    fg="#d8d8d8"
).pack(anchor="w", padx=20)

combo_modo = ttk.Combobox(left_panel, values=["SMC M15 Pro", "Zonas Básicas"], font=("Segoe UI", 11))
combo_modo.set("SMC M15 Pro")
combo_modo.pack(fill="x", padx=20, pady=(6, 20), ipady=7)

tk.Label(
    left_panel,
    text="Temporalidades básicas",
    font=("Segoe UI", 10, "bold"),
    bg="#151515",
    fg="#d8d8d8"
).pack(anchor="w", padx=20, pady=(8, 8))

tf_vars = {}
entries = {}

defaults = {
    "M1": "5",
    "M15": "10",
    "H1": "20",
    "H4": "30"
}

for tf in timeframes.keys():
    card = tk.Frame(left_panel, bg="#1d1d1d", padx=12, pady=10)
    card.pack(fill="x", padx=20, pady=5)

    var = tk.BooleanVar()
    if tf in ["M1", "M15", "H1"]:
        var.set(True)

    chk = tk.Checkbutton(
        card,
        text=tf,
        variable=var,
        font=("Segoe UI", 11, "bold"),
        bg="#1d1d1d",
        fg="white",
        selectcolor="#2a2a2a",
        activebackground="#1d1d1d",
        activeforeground="white"
    )
    chk.pack(side="left")

    entry = tk.Entry(
        card,
        width=7,
        font=("Segoe UI", 11),
        justify="center",
        bg="#292929",
        fg="white",
        insertbackground="white",
        relief="flat"
    )
    entry.insert(0, defaults[tf])
    entry.pack(side="right", ipady=6)

    tk.Label(
        card,
        text="días",
        font=("Segoe UI", 10),
        bg="#1d1d1d",
        fg="#bdbdbd"
    ).pack(side="right", padx=(0, 10))

    tf_vars[tf] = var
    entries[tf] = entry

btn = tk.Button(
    left_panel,
    text="ANALIZAR ZONAS",
    command=analizar,
    font=("Segoe UI", 12, "bold"),
    bg="#f2f2f2",
    fg="#111111",
    activebackground="#d8d8d8",
    activeforeground="#111111",
    relief="flat",
    pady=14,
    cursor="hand2"
)
btn.pack(fill="x", padx=20, pady=(24, 10))

btn_hist = tk.Button(
    left_panel,
    text="ACTUALIZAR HISTORIAL",
    command=cargar_historial,
    font=("Segoe UI", 10, "bold"),
    bg="#262626",
    fg="white",
    activebackground="#333333",
    activeforeground="white",
    relief="flat",
    pady=11,
    cursor="hand2"
)
btn_hist.pack(fill="x", padx=20, pady=(0, 10))

# Output card
tk.Label(
    right_panel,
    text="Resultado del análisis",
    font=("Segoe UI", 18, "bold"),
    bg="#0f0f0f",
    fg="white"
).pack(anchor="w", pady=(0, 10))

output = tk.Text(
    right_panel,
    font=("Consolas", 10),
    bg="#080808",
    fg="#f5f5f5",
    insertbackground="white",
    relief="flat",
    padx=18,
    pady=18,
    wrap="word"
)
output.pack(fill="both", expand=True)

# HISTORIAL TAB
hist_top = tk.Frame(tab_historial, bg="#0f0f0f")
hist_top.pack(fill="x", padx=18, pady=(18, 10))

tk.Label(
    hist_top,
    text="Historial de análisis guardados",
    font=("Segoe UI", 18, "bold"),
    bg="#0f0f0f",
    fg="white"
).pack(side="left")

tk.Button(
    hist_top,
    text="Actualizar",
    command=cargar_historial,
    font=("Segoe UI", 10, "bold"),
    bg="#f2f2f2",
    fg="#111111",
    relief="flat",
    padx=18,
    pady=8,
    cursor="hand2"
).pack(side="right")

historial_box = tk.Text(
    tab_historial,
    font=("Consolas", 10),
    bg="#080808",
    fg="#f5f5f5",
    relief="flat",
    padx=18,
    pady=18,
    wrap="word"
)
historial_box.pack(fill="both", expand=True, padx=18, pady=(0, 18))

# STATS TAB
stats_top = tk.Frame(tab_stats, bg="#0f0f0f")
stats_top.pack(fill="x", padx=18, pady=(18, 10))

tk.Label(
    stats_top,
    text="Estadísticas iniciales",
    font=("Segoe UI", 18, "bold"),
    bg="#0f0f0f",
    fg="white"
).pack(side="left")

tk.Button(
    stats_top,
    text="Calcular",
    command=cargar_estadisticas,
    font=("Segoe UI", 10, "bold"),
    bg="#f2f2f2",
    fg="#111111",
    relief="flat",
    padx=18,
    pady=8,
    cursor="hand2"
).pack(side="right")

stats_box = tk.Text(
    tab_stats,
    font=("Consolas", 10),
    bg="#080808",
    fg="#f5f5f5",
    relief="flat",
    padx=18,
    pady=18,
    wrap="word"
)
stats_box.pack(fill="both", expand=True, padx=18, pady=(0, 18))

# ARRANQUE
output.insert(tk.END, "GreenTrading listo.\nSelecciona índice y presiona ANALIZAR ZONAS.\n")
cargar_historial()

root.mainloop()
