import MetaTrader5 as mt5
import pandas as pd

symbol = "Boom 1000 Index"

if not mt5.initialize():
    print("No se pudo conectar ❌")
    print(mt5.last_error())
    quit()

# Asegurar que el símbolo esté disponible
if not mt5.symbol_select(symbol, True):
    print(f"No se pudo seleccionar el símbolo: {symbol}")
    print("Símbolos disponibles parecidos:")

    symbols = mt5.symbols_get()
    for s in symbols:
        if "Boom" in s.name or "Crash" in s.name:
            print("-", s.name)

    mt5.shutdown()
    quit()

rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 20)

df = pd.DataFrame(rates)
df["time"] = pd.to_datetime(df["time"], unit="s")

print(df)

mt5.shutdown()