#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mt5_to_supabase.py
Recolector local de velas de MetaTrader5 que las sube a Supabase.
Se ejecuta en PC local donde está instalado MT5.
"""

import os
import sys
import time
from datetime import datetime
import MetaTrader5 as mt5
import pandas as pd
import requests
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

# Validar credenciales
if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    print("❌ ERROR: No se encontró SUPABASE_URL o SUPABASE_ANON_KEY en .env")
    sys.exit(1)

# Configuración
SYMBOLS = [
    "Boom 1000 Index",
    "Boom 500 Index",
    "Crash 1000 Index",
    "Crash 500 Index"
]

TIMEFRAMES = {
    "M1": mt5.TIMEFRAME_M1,
    "M15": mt5.TIMEFRAME_M15,
    "H1": mt5.TIMEFRAME_H1
}

# Número de velas a recolectar por cada símbolo/timeframe
NUM_CANDLES = 100


def connect_mt5():
    """Conectar a MetaTrader5"""
    print("🔌 Conectando a MetaTrader5...")
    
    if not mt5.initialize():
        print("❌ Error al inicializar MT5")
        error = mt5.last_error()
        print(f"   Código de error: {error}")
        return False
    
    terminal_info = mt5.terminal_info()
    account_info = mt5.account_info()
    
    print(f"✅ Conectado a MT5")
    print(f"   Terminal: {terminal_info.name if terminal_info else 'N/A'}")
    print(f"   Cuenta: {account_info.login if account_info else 'N/A'}")
    
    return True


def get_available_symbols():
    """Obtener símbolos disponibles de Boom/Crash"""
    all_symbols = mt5.symbols_get()
    available = []
    
    for symbol_obj in all_symbols:
        name = symbol_obj.name
        if "Boom" in name or "Crash" in name or "boom" in name or "crash" in name:
            available.append(name)
    
    return available


def read_candles(symbol, timeframe_name, timeframe_mt5, num_candles):
    """Leer velas de MT5 para un símbolo y timeframe"""
    
    # Intentar seleccionar el símbolo
    if not mt5.symbol_select(symbol, True):
        print(f"⚠️  No se pudo seleccionar símbolo: {symbol}")
        return None
    
    # Obtener las velas
    rates = mt5.copy_rates_from_pos(symbol, timeframe_mt5, 0, num_candles)
    
    if rates is None or len(rates) == 0:
        print(f"⚠️  No hay datos para {symbol} en {timeframe_name}")
        return None
    
    # Convertir a DataFrame
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    
    return df


def format_candle_for_supabase(symbol, timeframe, row):
    """Formatear una vela para insertar en Supabase"""
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "timestamp": row["time"].isoformat(),
        "open": float(row["open"]),
        "high": float(row["high"]),
        "low": float(row["low"]),
        "close": float(row["close"]),
        "tick_volume": int(row["tick_volume"]),
        "spread": int(row["spread"]),
        "real_volume": int(row["real_volume"])
    }


def upload_to_supabase(candles_data):
    """Subir velas a Supabase tabla market_candles"""
    
    if not candles_data:
        print("⚠️  No hay datos para subir")
        return False
    
    url = f"{SUPABASE_URL}/rest/v1/market_candles"
    
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }
    
    try:
        response = requests.post(url, headers=headers, json=candles_data)
        
        if response.status_code in [200, 201]:
            print(f"   ✅ Subidas {len(candles_data)} velas a Supabase")
            return True
        else:
            print(f"   ❌ Error al subir: {response.status_code}")
            print(f"   Respuesta: {response.text[:200]}")
            return False
    
    except Exception as e:
        print(f"   ❌ Excepción al subir: {e}")
        return False


def collect_and_upload():
    """Proceso principal: recolectar y subir velas"""
    
    print("\n" + "="*60)
    print("🚀 INICIANDO RECOLECCIÓN DE VELAS MT5 → SUPABASE")
    print("="*60 + "\n")
    
    # Conectar a MT5
    if not connect_mt5():
        return False
    
    # Verificar símbolos disponibles
    print("\n📊 Verificando símbolos disponibles...")
    available_symbols = get_available_symbols()
    print(f"   Encontrados {len(available_symbols)} símbolos Boom/Crash:")
    for sym in available_symbols:
        print(f"   - {sym}")
    
    # Determinar qué símbolos usar
    symbols_to_use = []
    for symbol in SYMBOLS:
        if symbol in available_symbols:
            symbols_to_use.append(symbol)
        else:
            print(f"⚠️  Símbolo {symbol} no disponible, se omitirá")
    
    if not symbols_to_use:
        print("❌ No hay símbolos disponibles para recolectar")
        mt5.shutdown()
        return False
    
    print(f"\n📈 Símbolos a procesar: {len(symbols_to_use)}")
    
    # Recolectar velas
    total_uploaded = 0
    
    for symbol in symbols_to_use:
        print(f"\n📌 Procesando: {symbol}")
        
        for tf_name, tf_mt5 in TIMEFRAMES.items():
            print(f"   ⏰ Timeframe: {tf_name}")
            
            # Leer velas
            df = read_candles(symbol, tf_name, tf_mt5, NUM_CANDLES)
            
            if df is None:
                continue
            
            # Formatear para Supabase
            candles_batch = []
            for _, row in df.iterrows():
                candle = format_candle_for_supabase(symbol, tf_name, row)
                candles_batch.append(candle)
            
            # Subir a Supabase
            if upload_to_supabase(candles_batch):
                total_uploaded += len(candles_batch)
    
    # Cerrar conexión MT5
    mt5.shutdown()
    print("\n" + "="*60)
    print(f"✅ PROCESO COMPLETADO")
    print(f"   Total de velas subidas: {total_uploaded}")
    print("="*60 + "\n")
    
    return True


def main():
    """Función principal"""
    try:
        collect_and_upload()
    except KeyboardInterrupt:
        print("\n\n⚠️  Proceso interrumpido por el usuario")
        mt5.shutdown()
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ ERROR INESPERADO: {e}")
        mt5.shutdown()
        sys.exit(1)


if __name__ == "__main__":
    main()
