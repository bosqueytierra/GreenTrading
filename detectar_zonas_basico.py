import MetaTrader5 as mt5
import pandas as pd

symbol = "Boom 1000 Index"

mt5.initialize()

rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 300)
df = pd.DataFrame(rates)
df["time"] = pd.to_datetime(df["time"], unit="s")

mt5.shutdown()

# -----------------------------
# DETECCIÓN BÁSICA DE ZONAS
# -----------------------------

zonas = []

for i in range(2, len(df)-2):
    high = df["high"][i]
    low = df["low"][i]

    # detectar máximo local
    if high > df["high"][i-1] and high > df["high"][i+1]:
        zonas.append({
            "tipo": "resistencia",
            "precio": high,
            "time": df["time"][i]
        })

    # detectar mínimo local
    if low < df["low"][i-1] and low < df["low"][i+1]:
        zonas.append({
            "tipo": "soporte",
            "precio": low,
            "time": df["time"][i]
        })

# mostrar zonas
for z in zonas[-10:]:
    print(z)


# -----------------------------
# AGRUPAR ZONAS CERCANAS
# -----------------------------

zonas_agrupadas = []

tolerancia = 10  # puntos de cercanía

for z in zonas:
    encontrado = False

    for grupo in zonas_agrupadas:
        if abs(grupo["precio"] - z["precio"]) < tolerancia:
            grupo["conteo"] += 1
            grupo["precio"] = (grupo["precio"] + z["precio"]) / 2
            encontrado = True
            break

    if not encontrado:
        zonas_agrupadas.append({
            "tipo": z["tipo"],
            "precio": z["precio"],
            "conteo": 1
        })

# mostrar zonas fuertes
print("\nZONAS AGRUPADAS:")
for g in zonas_agrupadas:
    if g["conteo"] >= 2:
        print(g)



# -----------------------------
# PRECIO ACTUAL
# -----------------------------

precio_actual = df["close"].iloc[-1]

print("\nPRECIO ACTUAL:", precio_actual)

# -----------------------------
# VER ZONAS CERCANAS
# -----------------------------

print("\nZONAS CERCANAS:")

for g in zonas_agrupadas:
    distancia = abs(g["precio"] - precio_actual)

    if distancia < 20:  # rango de cercanía
        print({
            "tipo": g["tipo"],
            "precio": g["precio"],
            "conteo": g["conteo"],
            "distancia": distancia
        })



print("\nLECTURA DE ZONAS CERCANAS:")

for g in zonas_agrupadas:
    distancia = abs(g["precio"] - precio_actual)

    if distancia < 20:
        if g["conteo"] >= 8:
            fuerza = "FUERTE"
        elif g["conteo"] >= 4:
            fuerza = "MEDIA"
        elif g["conteo"] >= 2:
            fuerza = "DEBIL"
        else:
            fuerza = "RUIDO"

        print({
            "tipo": g["tipo"],
            "precio": round(float(g["precio"]), 3),
            "conteo": int(g["conteo"]),
            "distancia": round(float(distancia), 3),
            "fuerza": fuerza
        })