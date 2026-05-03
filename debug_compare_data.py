#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
debug_compare_data.py
Comparar la data M15 de MT5 vs Supabase para un índice.
"""

import os
import MetaTrader5 as mt5
import pandas as pd
import requests
from dotenv import load_dotenv
from datetime import datetime

# Cargar variables de entorno
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

# Parámetros
symbol = "Boom 900 Index"
timeframe = "M15"
candles = 800

# Validar credenciales
if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    print("❌ ERROR: No se encontró SUPABASE_URL o SUPABASE_ANON_KEY en .env")
    exit(1)


def connect_mt5():
    """Conectar a MetaTrader5"""
    if not mt5.initialize():
        error = mt5.last_error()
        print(f"❌ Error MT5: {error}")
        return False
    
    print("✅ MT5 conectado correctamente")
    return True


def read_candles_from_mt5(symbol, num_candles):
    """Leer las últimas velas M15 desde MT5"""
    
    # Intentar seleccionar el símbolo
    if not mt5.symbol_select(symbol, True):
        print(f"❌ No se pudo seleccionar símbolo: {symbol}")
        print("\nSímbolos disponibles parecidos:")
        symbols = mt5.symbols_get()
        for s in symbols:
            if "Boom" in s.name or "Crash" in s.name:
                print(f"  - {s.name}")
        return None
    
    # Obtener las velas M15
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, num_candles)
    
    if rates is None or len(rates) == 0:
        print(f"⚠️ MT5 no devolvió velas para {symbol} [M15]")
        return None
    
    # Convertir a DataFrame
    df = pd.DataFrame(rates)
    # Convertir time a datetime UTC
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    
    return df


def read_candles_from_supabase(symbol, timeframe, num_candles):
    """Leer las últimas velas desde Supabase tabla market_candles"""
    
    url = f"{SUPABASE_URL}/rest/v1/market_candles"
    
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json"
    }
    
    params = {
        "symbol": f"eq.{symbol}",
        "timeframe": f"eq.{timeframe}",
        "select": "timestamp,open,high,low,close,tick_volume,spread,real_volume",
        "order": "timestamp.desc",
        "limit": str(num_candles)
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            
            if not data or len(data) == 0:
                print(f"⚠️ No se encontraron datos en Supabase para {symbol} [{timeframe}]")
                return None
            
            # Convertir a DataFrame
            df = pd.DataFrame(data)
            # Convertir timestamp a datetime UTC
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            
            return df
        else:
            print(f"❌ Error al consultar Supabase: {response.status_code}")
            print(f"Respuesta: {response.text}")
            return None
    
    except Exception as e:
        print(f"❌ Error al consultar Supabase: {e}")
        return None


def compare_data(df_mt5, df_supabase):
    """Comparar las velas de MT5 vs Supabase"""
    
    print("\n" + "="*80)
    print("COMPARACIÓN DE DATOS MT5 vs SUPABASE")
    print("="*80)
    
    # Mostrar cantidades
    print(f"\n📊 CANTIDAD DE VELAS:")
    print(f"   MT5:       {len(df_mt5)}")
    print(f"   Supabase:  {len(df_supabase)}")
    
    # Ordenar ambas por timestamp ascendente
    df_mt5_sorted = df_mt5.sort_values("time").reset_index(drop=True)
    df_supabase_sorted = df_supabase.sort_values("timestamp").reset_index(drop=True)
    
    # Mostrar primera y última vela de cada fuente
    print(f"\n🕐 PRIMERA VELA MT5:")
    print(f"   Timestamp: {df_mt5_sorted.iloc[0]['time']}")
    print(f"   O: {df_mt5_sorted.iloc[0]['open']:.3f}  H: {df_mt5_sorted.iloc[0]['high']:.3f}  "
          f"L: {df_mt5_sorted.iloc[0]['low']:.3f}  C: {df_mt5_sorted.iloc[0]['close']:.3f}")
    
    print(f"\n🕐 PRIMERA VELA SUPABASE:")
    print(f"   Timestamp: {df_supabase_sorted.iloc[0]['timestamp']}")
    print(f"   O: {df_supabase_sorted.iloc[0]['open']:.3f}  H: {df_supabase_sorted.iloc[0]['high']:.3f}  "
          f"L: {df_supabase_sorted.iloc[0]['low']:.3f}  C: {df_supabase_sorted.iloc[0]['close']:.3f}")
    
    print(f"\n🕐 ÚLTIMA VELA MT5:")
    print(f"   Timestamp: {df_mt5_sorted.iloc[-1]['time']}")
    print(f"   O: {df_mt5_sorted.iloc[-1]['open']:.3f}  H: {df_mt5_sorted.iloc[-1]['high']:.3f}  "
          f"L: {df_mt5_sorted.iloc[-1]['low']:.3f}  C: {df_mt5_sorted.iloc[-1]['close']:.3f}")
    
    print(f"\n🕐 ÚLTIMA VELA SUPABASE:")
    print(f"   Timestamp: {df_supabase_sorted.iloc[-1]['timestamp']}")
    print(f"   O: {df_supabase_sorted.iloc[-1]['open']:.3f}  H: {df_supabase_sorted.iloc[-1]['high']:.3f}  "
          f"L: {df_supabase_sorted.iloc[-1]['low']:.3f}  C: {df_supabase_sorted.iloc[-1]['close']:.3f}")
    
    # Crear diccionarios indexados por timestamp para comparación
    mt5_dict = {}
    for _, row in df_mt5_sorted.iterrows():
        ts = row["time"]
        mt5_dict[ts] = {
            "open": row["open"],
            "high": row["high"],
            "low": row["low"],
            "close": row["close"]
        }
    
    supabase_dict = {}
    for _, row in df_supabase_sorted.iterrows():
        ts = row["timestamp"]
        supabase_dict[ts] = {
            "open": row["open"],
            "high": row["high"],
            "low": row["low"],
            "close": row["close"]
        }
    
    # Comparar timestamp por timestamp
    all_timestamps = sorted(set(mt5_dict.keys()) | set(supabase_dict.keys()))
    
    coincidencias = 0
    diferencias = []
    
    for ts in all_timestamps:
        in_mt5 = ts in mt5_dict
        in_supabase = ts in supabase_dict
        
        if in_mt5 and in_supabase:
            # Comparar valores con tolerancia de 0.001
            mt5_data = mt5_dict[ts]
            supabase_data = supabase_dict[ts]
            
            match = (
                abs(mt5_data["open"] - supabase_data["open"]) < 0.001 and
                abs(mt5_data["high"] - supabase_data["high"]) < 0.001 and
                abs(mt5_data["low"] - supabase_data["low"]) < 0.001 and
                abs(mt5_data["close"] - supabase_data["close"]) < 0.001
            )
            
            if match:
                coincidencias += 1
            else:
                diferencias.append({
                    "timestamp": ts,
                    "mt5": mt5_data,
                    "supabase": supabase_data,
                    "tipo": "VALORES_DIFERENTES"
                })
        elif in_mt5:
            diferencias.append({
                "timestamp": ts,
                "mt5": mt5_dict[ts],
                "supabase": None,
                "tipo": "SOLO_EN_MT5"
            })
        else:
            diferencias.append({
                "timestamp": ts,
                "mt5": None,
                "supabase": supabase_dict[ts],
                "tipo": "SOLO_EN_SUPABASE"
            })
    
    # Resultados de comparación
    print(f"\n📈 RESULTADOS DE COMPARACIÓN:")
    print(f"   Total de timestamps únicos: {len(all_timestamps)}")
    print(f"   Velas coincidentes:          {coincidencias}")
    print(f"   Velas con diferencias:       {len(diferencias)}")
    
    # Mostrar las primeras 20 diferencias
    if diferencias:
        print(f"\n⚠️  PRIMERAS 20 DIFERENCIAS:")
        print("-" * 80)
        
        for i, diff in enumerate(diferencias[:20]):
            print(f"\n#{i+1} - {diff['tipo']}")
            print(f"   Timestamp: {diff['timestamp']}")
            
            if diff["mt5"]:
                print(f"   MT5:       O: {diff['mt5']['open']:.3f}  H: {diff['mt5']['high']:.3f}  "
                      f"L: {diff['mt5']['low']:.3f}  C: {diff['mt5']['close']:.3f}")
            else:
                print(f"   MT5:       (no existe)")
            
            if diff["supabase"]:
                print(f"   Supabase:  O: {diff['supabase']['open']:.3f}  H: {diff['supabase']['high']:.3f}  "
                      f"L: {diff['supabase']['low']:.3f}  C: {diff['supabase']['close']:.3f}")
            else:
                print(f"   Supabase:  (no existe)")
    else:
        print(f"\n✅ ¡Todas las velas coinciden perfectamente!")
    
    print("\n" + "="*80)


def main():
    """Función principal"""
    
    print("="*80)
    print("🔍 DEBUG: COMPARACIÓN MT5 vs SUPABASE")
    print("="*80)
    print(f"Symbol:    {symbol}")
    print(f"Timeframe: {timeframe}")
    print(f"Candles:   {candles}")
    print("="*80)
    
    # 1. Conectar a MT5
    print("\n1️⃣  Conectando a MT5...")
    if not connect_mt5():
        print("❌ No se pudo conectar a MT5. Verifica que esté instalado y ejecutándose.")
        return
    
    # 2. Leer velas de MT5
    print(f"\n2️⃣  Leyendo {candles} velas M15 desde MT5...")
    df_mt5 = read_candles_from_mt5(symbol, candles)
    
    if df_mt5 is None:
        print("❌ No se pudieron leer las velas de MT5")
        mt5.shutdown()
        return
    
    print(f"✅ Obtenidas {len(df_mt5)} velas de MT5")
    
    # 3. Leer velas de Supabase
    print(f"\n3️⃣  Leyendo {candles} velas M15 desde Supabase...")
    df_supabase = read_candles_from_supabase(symbol, timeframe, candles)
    
    if df_supabase is None:
        print("❌ No se pudieron leer las velas de Supabase")
        mt5.shutdown()
        return
    
    print(f"✅ Obtenidas {len(df_supabase)} velas de Supabase")
    
    # 4. Comparar datos
    print(f"\n4️⃣  Comparando datos...")
    compare_data(df_mt5, df_supabase)
    
    # Cerrar MT5
    mt5.shutdown()
    print("\n✅ MT5 desconectado")
    
    print("\n" + "="*80)
    print("🏁 DIAGNÓSTICO COMPLETADO")
    print("="*80)


if __name__ == "__main__":
    main()
