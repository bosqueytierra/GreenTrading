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
    "Boom 900 Index",
    "Boom 600 Index",
    "Boom 500 Index",
    "Boom 300 Index",
    "Crash 1000 Index",
    "Crash 900 Index",
    "Crash 600 Index",
    "Crash 500 Index",
    "Crash 300 Index"
]

TIMEFRAMES = {
    "M1": mt5.TIMEFRAME_M1,
    "M15": mt5.TIMEFRAME_M15,
    "H1": mt5.TIMEFRAME_H1
}

# Configuración de velas por timeframe para carga inicial
INITIAL_CANDLES_BY_TIMEFRAME = {
    "M1": 10000,
    "M15": 2000,
    "H1": 700
}

# Configuración de margen de seguridad por timeframe
SAFETY_MARGIN = {
    "M1": 10,
    "M15": 5,
    "H1": 3
}

# Configuración de mínimo de lectura por timeframe
MIN_CANDLES_TO_READ = {
    "M1": 20,
    "M15": 10,
    "H1": 5
}

# Minutos por vela según timeframe
MINUTES_PER_CANDLE = {
    "M1": 1,
    "M15": 15,
    "H1": 60
}

# Intervalo de sincronización (3 minutos)
SYNC_INTERVAL_SECONDS = 180


def connect_mt5():
    """Conectar a MetaTrader5"""
    if not mt5.initialize():
        error = mt5.last_error()
        print(f"❌ Error MT5: {error}")
        return False
    
    print("✅ MT5 conectado")
    return True


def get_last_timestamp_from_supabase(symbol, timeframe):
    """
    Consultar el último timestamp guardado en Supabase para un symbol/timeframe.
    Retorna None si no hay datos previos, o el timestamp como string ISO.
    """
    url = f"{SUPABASE_URL}/rest/v1/market_candles"
    
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json"
    }
    
    params = {
        "symbol": f"eq.{symbol}",
        "timeframe": f"eq.{timeframe}",
        "select": "timestamp",
        "order": "timestamp.desc",
        "limit": "1"
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                return data[0]["timestamp"]
            else:
                return None
        else:
            print(f"⚠️ Error al consultar último timestamp: {response.status_code}")
            return None
    
    except Exception as e:
        print(f"❌ Error al consultar Supabase: {e}")
        return None


def calculate_candles_to_read(last_timestamp, timeframe_name):
    """
    Calcular cuántas velas leer según el tiempo transcurrido desde el último timestamp.
    
    Args:
        last_timestamp: timestamp ISO string del último dato guardado
        timeframe_name: nombre del timeframe (M1, M15, H1)
    
    Returns:
        Número de velas a leer con margen de seguridad aplicado
    """
    # Convertir last_timestamp a datetime UTC-aware
    last_dt = pd.to_datetime(last_timestamp, utc=True)
    now_dt = pd.Timestamp.now(tz='UTC')
    
    # Calcular minutos transcurridos
    elapsed_minutes = (now_dt - last_dt).total_seconds() / 60.0
    
    # Obtener minutos por vela según timeframe
    minutes_per_candle = MINUTES_PER_CANDLE[timeframe_name]
    
    # Calcular velas estimadas
    estimated_candles = int(elapsed_minutes / minutes_per_candle)
    
    # Agregar margen de seguridad
    candles_with_margin = estimated_candles + SAFETY_MARGIN[timeframe_name]
    
    # Aplicar mínimo
    final_candles = max(candles_with_margin, MIN_CANDLES_TO_READ[timeframe_name])
    
    return final_candles





def read_candles(symbol, timeframe_name, timeframe_mt5, num_candles):
    """Leer velas de MT5 para un símbolo y timeframe"""
    
    # Intentar seleccionar el símbolo
    if not mt5.symbol_select(symbol, True):
        print(f"❌ No se pudo seleccionar símbolo: {symbol}")
        return None
    
    # Obtener las velas
    rates = mt5.copy_rates_from_pos(symbol, timeframe_mt5, 0, num_candles)
    
    if rates is None or len(rates) == 0:
        print(f"⚠️ MT5 no devolvió velas para {symbol} [{timeframe_name}]")
        return None
    
    print(f"📊 {symbol} [{timeframe_name}]: {len(rates)} velas")
    
    # Convertir a DataFrame
    df = pd.DataFrame(rates)
    # Convertir time a UTC-aware datetime para compatibilidad con Supabase
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    
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
    """Subir velas a Supabase tabla market_candles usando POST normal"""
    
    if not candles_data:
        return False
    
    # POST normal sin upsert
    url = f"{SUPABASE_URL}/rest/v1/market_candles"
    
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    
    try:
        response = requests.post(url, headers=headers, json=candles_data)
        
        # Considerar éxito si el status es 200, 201 o 204
        if response.status_code in [200, 201, 204]:
            return True
        else:
            print(f"❌ Supabase rechazó la subida")
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    
    except Exception as e:
        print(f"❌ Error al subir a Supabase: {e}")
        return False


def collect_and_upload():
    """Proceso principal: recolectar y subir velas"""
    
    # Usar directamente la lista SYMBOLS sin filtrar
    # Recolectar velas
    total_uploaded = 0
    
    for symbol in SYMBOLS:
        for tf_name, tf_mt5 in TIMEFRAMES.items():
            # 1. Consultar el último timestamp guardado en Supabase
            last_timestamp = get_last_timestamp_from_supabase(symbol, tf_name)
            
            # 2. Si NO existe último timestamp: subir carga inicial usando configuración por timeframe
            if last_timestamp is None:
                num_candles = INITIAL_CANDLES_BY_TIMEFRAME[tf_name]
                df = read_candles(symbol, tf_name, tf_mt5, num_candles)
                
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
                    print(f"✅ Carga inicial: {symbol} [{tf_name}] - {len(candles_batch)} velas")
            
            # 3. Si SÍ existe último timestamp: calcular dinámicamente cuántas velas leer
            else:
                # Calcular cuántas velas leer según tiempo transcurrido
                num_candles = calculate_candles_to_read(last_timestamp, tf_name)
                df = read_candles(symbol, tf_name, tf_mt5, num_candles)
                
                if df is None:
                    continue
                
                # Convertir last_timestamp a datetime UTC-aware para comparación
                last_dt = pd.to_datetime(last_timestamp, utc=True)
                
                # Filtrar solo velas con timestamp > último guardado
                df_new = df[df["time"] > last_dt]
                
                # Si no hay velas nuevas, mostrar log y continuar
                if len(df_new) == 0:
                    print(f"Sin velas nuevas: {symbol} {tf_name}")
                    continue
                
                # Formatear para Supabase
                candles_batch = []
                for _, row in df_new.iterrows():
                    candle = format_candle_for_supabase(symbol, tf_name, row)
                    candles_batch.append(candle)
                
                # Subir solo las nuevas a Supabase
                if upload_to_supabase(candles_batch):
                    total_uploaded += len(candles_batch)
                    print(f"✅ {symbol} [{tf_name}] - {len(candles_batch)} velas nuevas")
    
    print(f"✅ Subidas {total_uploaded} velas - {datetime.now().strftime('%H:%M:%S')}")
    return True


def run_forever():
    """Ejecutar recolección en loop cada SYNC_INTERVAL_SECONDS"""
    print(f"🔄 Iniciando recolector (intervalo: {SYNC_INTERVAL_SECONDS}s)")
    
    # Conectar a MT5 una sola vez al inicio
    if not connect_mt5():
        print("❌ No se pudo conectar a MT5")
        return
    
    try:
        while True:
            try:
                collect_and_upload()
            except Exception as e:
                print(f"⚠️ Error en ciclo: {e}")
            
            # Esperar antes del próximo ciclo
            time.sleep(SYNC_INTERVAL_SECONDS)
    
    except KeyboardInterrupt:
        print("\n⚠️ Detenido por usuario")
    finally:
        mt5.shutdown()
        print("✅ MT5 cerrado")


def main():
    """Función principal"""
    run_forever()


if __name__ == "__main__":
    main()
