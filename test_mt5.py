import MetaTrader5 as mt5

print("Probando conexión con MetaTrader 5...")

if not mt5.initialize():
    print("No se pudo conectar ❌")
    print("Error:", mt5.last_error())
else:
    print("Conectado a MT5 ✅")
    print("Terminal:", mt5.terminal_info())
    print("Cuenta:", mt5.account_info())
    mt5.shutdown()