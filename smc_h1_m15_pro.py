"""
SMC PRO TENDENCIA H1 + CHOCH/BOS (M15)

Nueva estrategia basada en SMC M15 PRO con validación adicional:
1. Tendencia H1 acorde al tipo de índice
2. Último evento M15 acorde a la dirección operativa

NO MODIFICA la estrategia SMC M15 PRO original.
Usa módulo separado smc_engine_h1_m15.py
"""

import MetaTrader5 as mt5
import pandas as pd
from src.smc_engine_h1_m15 import analyze_smc_h1_m15

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
    """Obtiene datos de MT5 para un símbolo y timeframe específico."""
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, candles)

    if rates is None:
        return pd.DataFrame()

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df


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

    # Analizar con nueva estrategia H1 + M15
    result = analyze_smc_h1_m15(SYMBOL, df_h1, df_m15)

    tendencia_h1 = result["tendencia_h1"]
    tendencia_m15 = result["tendencia_m15"]
    eventos_h1 = result["eventos_h1"]
    eventos_m15 = result["eventos_m15"]
    zona = result["zona"]
    precio_actual = result["precio_actual"]
    es_valido = result["es_valido"]
    razon_validacion = result["razon_validacion"]

    print("\n" + "="*60)
    print(" SMC PRO TENDENCIA H1 + CHOCH/BOS (M15)")
    print("="*60)
    print(f"Índice: {SYMBOL}")
    print(f"Precio actual: {round(precio_actual, 3) if precio_actual else 'N/A'}")
    print("-"*60)
    print(f"Tendencia H1: {tendencia_h1}")
    print(f"Tendencia M15: {tendencia_m15}")

    if eventos_h1:
        print(f"Último evento H1: {eventos_h1[-1]['evento']} | nivel: {round(eventos_h1[-1]['nivel_roto'], 3)}")

    if eventos_m15:
        print(f"Último evento M15: {eventos_m15[-1]['evento']} | nivel: {round(eventos_m15[-1]['nivel_roto'], 3)}")

    print("-"*60)

    # Mostrar validación H1 + M15
    print(f"\n🔍 VALIDACIÓN H1 + M15:")
    print(f"Estado: {'✅ VÁLIDO' if es_valido else '❌ DESCARTADO'}")
    print(f"Razón: {razon_validacion}")
    print("-"*60)

    if not zona:
        print("\nNo hay zona M15 depurada por ahora.")
    else:
        print("\nZONA DEPURADA M15:")
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

        if es_valido:
            if zona["zona_desde"] <= precio_actual <= zona["zona_hasta"]:
                print("\nESTADO: PRECIO DENTRO DE ZONA ⚠️")
            else:
                distancia = min(
                    abs(precio_actual - zona["zona_desde"]),
                    abs(precio_actual - zona["zona_hasta"])
                )
                print(f"\nESTADO: Precio fuera de zona | distancia aprox: {round(distancia, 3)}")
        else:
            print("\nESTADO: ZONA DESCARTADA (No cumple validación H1 + M15)")

    print("="*60)
    mt5.shutdown()


if __name__ == "__main__":
    main()
