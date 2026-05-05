#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SMC_TENDENCY_H1_M15 - Procesador de Supabase

ESTRATEGIA NUEVA desde cero.

Este procesador:
1. Lee velas desde public.market_candles (misma fuente que otras estrategias)
2. Ejecuta análisis SMC con validación SOLO: Dirección índice + H1 + Evento M15
3. Guarda resultados SOLO en: public.smc_tendency_h1_m15_setups

IMPORTANTE:
- NO valida tendencia M15 (solo informativa)
- Solo guarda zonas VÁLIDAS (no hay registros DESCARTADA)
- Usa tabla exclusiva: public.smc_tendency_h1_m15_setups
- NO toca: public.smc_m15_setups ni public.smc_h1_m15_setups

Estados permitidos: ACTIVA, EN_ZONA, PROFIT, PAUSADA, TP, SL
NO usa: DESCARTADA (zonas inválidas simplemente no se guardan)
"""

import os
import sys
import time
import pandas as pd
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv
from src.smc_engine_tendency_h1_m15 import analyze_smc_tendency_h1_m15

# Cargar variables de entorno
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

# ⚠️ TABLA OBLIGATORIA - NO MODIFICAR
# Esta estrategia SOLO usa smc_tendency_h1_m15_setups
TARGET_TABLE = "smc_tendency_h1_m15_setups"

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

# Velas a obtener por timeframe
CANDLES_BY_TIMEFRAME = {
    "H1": 500,
    "M15": 800,
    "M1": 200  # Opcional, si se usa refinamiento M1
}

# Intervalo de procesamiento (en segundos)
PROCESS_INTERVAL_SECONDS = 180  # 3 minutos

# Umbral de similitud de zona (en puntos)
ZONE_SIMILARITY_THRESHOLD = 10  # Diferencia máxima para considerar zonas similares

# Estados terminales (zonas cerradas)
TERMINAL_STATES = {"TP", "SL", "PROFIT", "PAUSADA"}

# =========================
# SUPABASE HELPERS
# =========================

def supabase_headers():
    """Genera headers para requests a Supabase"""
    return {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }


def get_zone_boundaries(zona_desde, zona_hasta):
    """
    Calcula los límites (mínimo y máximo) de una zona.
    
    Funciona para zonas alcistas y bajistas independientemente del orden
    en que se proporcionen zona_desde y zona_hasta.
    
    Args:
        zona_desde: Límite inferior o superior de la zona
        zona_hasta: Límite superior o inferior de la zona
    
    Returns:
        Tupla (zona_min, zona_max)
    """
    return min(zona_desde, zona_hasta), max(zona_desde, zona_hasta)


def calculate_zone_size(zona_desde, zona_hasta):
    """
    Calcula el tamaño de una zona en puntos.
    
    Args:
        zona_desde: Límite inferior o superior de la zona
        zona_hasta: Límite superior o inferior de la zona
    
    Returns:
        Tamaño absoluto de la zona en puntos
    """
    return abs(zona_hasta - zona_desde)


def calculate_tp_sl_prices(zona, direccion):
    """
    Calcula los precios de TP y SL con ratio 1:1.
    
    Para zonas alcistas:
    - Entrada: zona_desde (parte baja de la zona)
    - SL: zona_desde - zona_size (por debajo de la zona)
    - TP: zona_hasta + zona_size (por encima de la zona)
    
    Para zonas bajistas:
    - Entrada: zona_hasta (parte alta de la zona)
    - SL: zona_hasta + zona_size (por encima de la zona)
    - TP: zona_desde - zona_size (por debajo de la zona)
    
    Args:
        zona: Diccionario con zona_desde y zona_hasta
        direccion: "ALCISTA" o "BAJISTA"
    
    Returns:
        Tupla (precio_entrada, sl_price, tp_price)
    """
    zona_size = calculate_zone_size(zona['zona_desde'], zona['zona_hasta'])
    
    if direccion == "ALCISTA":
        precio_entrada = zona['zona_desde']
        sl_price = zona['zona_desde'] - zona_size
        tp_price = zona['zona_hasta'] + zona_size
    else:
        precio_entrada = zona['zona_hasta']
        sl_price = zona['zona_hasta'] + zona_size
        tp_price = zona['zona_desde'] - zona_size
    
    return precio_entrada, sl_price, tp_price



def get_candles_from_supabase(symbol, timeframe, limit=1000):
    """
    Obtiene velas desde public.market_candles en Supabase.
    
    Args:
        symbol: Símbolo del índice
        timeframe: Timeframe (H1, M15, M1)
        limit: Número máximo de velas a obtener
    
    Returns:
        DataFrame con columnas [time, open, high, low, close, tick_volume, spread, real_volume]
    """
    url = (
        f"{SUPABASE_URL}/rest/v1/market_candles"
        f"?symbol=eq.{symbol}"
        f"&timeframe=eq.{timeframe}"
        f"&order=timestamp.desc"
        f"&limit={limit}"
    )
    
    try:
        response = requests.get(url, headers=supabase_headers(), timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Error obteniendo velas {symbol} {timeframe}: {response.status_code}")
            return pd.DataFrame()
        
        data = response.json()
        
        if not data:
            print(f"⚠️  No hay velas para {symbol} {timeframe}")
            return pd.DataFrame()
        
        # Convertir a DataFrame
        df = pd.DataFrame(data)
        
        # Ordenar por timestamp ascendente (más antiguo primero)
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        # Renombrar columnas para compatibilidad con smc_engine
        df = df.rename(columns={'timestamp': 'time'})
        
        # Convertir timestamp a datetime
        df['time'] = pd.to_datetime(df['time'])
        
        # Asegurar que tenemos las columnas necesarias
        required_cols = ['time', 'open', 'high', 'low', 'close']
        if not all(col in df.columns for col in required_cols):
            print(f"❌ Faltan columnas requeridas en {symbol} {timeframe}")
            return pd.DataFrame()
        
        return df
    
    except Exception as e:
        print(f"❌ Error conectando a Supabase para {symbol} {timeframe}: {e}")
        return pd.DataFrame()


def get_active_zones_for_symbol(symbol):
    """
    Obtiene zonas activas para un símbolo específico.
    
    ⚠️ Lee SOLO de smc_tendency_h1_m15_setups (estrategia SMC_TENDENCY_H1_M15)
    
    Args:
        symbol: Símbolo del índice
    
    Returns:
        Lista de zonas activas
    """
    url = (
        f"{SUPABASE_URL}/rest/v1/{TARGET_TABLE}"
        f"?symbol=eq.{symbol}"
        f"&estado=eq.ACTIVA"
        f"&select=*"
    )
    
    try:
        response = requests.get(url, headers=supabase_headers(), timeout=15)
        
        if response.status_code == 200:
            return response.json()
        
        return []
    
    except Exception as e:
        print(f"❌ Error obteniendo zonas activas para {symbol}: {e}")
        return []


def pause_zone(zone_id, motivo="Pausada por nueva zona activa"):
    """
    Pausa una zona existente.
    
    ⚠️ Actualiza SOLO en smc_tendency_h1_m15_setups (estrategia SMC_TENDENCY_H1_M15)
    
    Args:
        zone_id: ID de la zona a pausar
        motivo: Motivo del cierre
    """
    url = f"{SUPABASE_URL}/rest/v1/{TARGET_TABLE}?id=eq.{zone_id}"
    
    data = {
        "estado": "PAUSADA",
        "fecha_cierre": datetime.now(timezone.utc).isoformat(),
        "motivo_cierre": motivo
    }
    
    try:
        response = requests.patch(url, headers=supabase_headers(), json=data, timeout=15)
        
        if response.status_code in [200, 204]:
            print(f"  ⏸️  Zona {zone_id} pausada")
            return True
        
        print(f"  ❌ Error pausando zona {zone_id}: {response.status_code}")
        return False
    
    except Exception as e:
        print(f"  ❌ Error pausando zona {zone_id}: {e}")
        return False


def save_zone_to_supabase(symbol, result, zona):
    """
    Guarda una zona en public.smc_tendency_h1_m15_setups.
    
    ⚠️ SOLO guarda zonas VÁLIDAS (es_valido = True)
    ⚠️ Inserta SOLO en smc_tendency_h1_m15_setups
    ⚠️ NUNCA insertar en smc_m15_setups ni smc_h1_m15_setups
    
    Args:
        symbol: Símbolo del índice
        result: Resultado del análisis SMC
        zona: Zona depurada M15
    
    Returns:
        True si se guardó exitosamente, False si no
    """
    # REGLA ABSOLUTA: Solo guardar si es_valido = True
    if not result['es_valido']:
        print(f"  ⚠️  Zona NO guardada: {symbol} - {result['razon_validacion']}")
        return False
    
    tipo_indice = "BOOM" if "Boom" in symbol else "CRASH"
    
    # Calcular TP y SL (ratio 1:1) usando helper
    zona_size = calculate_zone_size(zona['zona_desde'], zona['zona_hasta'])
    precio_entrada, sl_price, tp_price = calculate_tp_sl_prices(zona, zona['direccion'])
    
    data = {
        "symbol": symbol,
        "tipo_indice": tipo_indice,
        "direccion": zona['direccion'],
        "fecha_detectada": datetime.now(timezone.utc).isoformat(),
        "zona_desde": zona['zona_desde'],
        "zona_hasta": zona['zona_hasta'],
        "zona_size_puntos": zona_size,
        "precio_actual_detectado": result['precio_actual'],
        "precio_entrada_referencia": precio_entrada,
        "score": zona['score'],
        "evento": zona['evento']['evento'],
        "ob": bool(zona['ob']),
        "fvg": bool(zona['fvg']),
        "barrida": bool(zona['barrida']),
        "estado": "ACTIVA",
        "tp_price": tp_price,
        "sl_price": sl_price,
        "ratio_rr": 1.0,
        "max_reaccion_puntos": 0.0,
        "resultado_puntos": None,
        "fecha_cierre": None,
        "motivo_cierre": None,
        "tendencia_h1": result['tendencia_h1'],
        "tendencia_m15": result['tendencia_m15'],  # Solo informativa
        "strategy": "SMC_TENDENCY_H1_M15"
    }
    
    url = f"{SUPABASE_URL}/rest/v1/{TARGET_TABLE}"
    
    try:
        response = requests.post(url, headers=supabase_headers(), json=data, timeout=15)
        
        if response.status_code in [200, 201]:
            print(f"  ✅ Zona guardada: {symbol} {zona['direccion']} (ACTIVA)")
            return True
        
        print(f"  ❌ Error guardando zona {symbol}: {response.status_code} - {response.text}")
        return False
    
    except Exception as e:
        print(f"  ❌ Error guardando zona {symbol}: {e}")
        return False


def update_zone_state(zone_id, new_state, precio_actual, motivo=None):
    """
    Actualiza el estado de una zona.
    
    ⚠️ Actualiza SOLO en smc_tendency_h1_m15_setups (estrategia SMC_TENDENCY_H1_M15)
    
    Args:
        zone_id: ID de la zona
        new_state: Nuevo estado
        precio_actual: Precio actual
        motivo: Motivo del cambio (opcional)
    """
    url = f"{SUPABASE_URL}/rest/v1/{TARGET_TABLE}?id=eq.{zone_id}"
    
    data = {
        "estado": new_state
    }
    
    if new_state in TERMINAL_STATES:
        data["fecha_cierre"] = datetime.now(timezone.utc).isoformat()
        if motivo:
            data["motivo_cierre"] = motivo
    
    try:
        response = requests.patch(url, headers=supabase_headers(), json=data, timeout=15)
        
        if response.status_code in [200, 204]:
            print(f"  🔄 Zona {zone_id} actualizada a {new_state}")
            return True
        
        return False
    
    except Exception as e:
        print(f"  ❌ Error actualizando zona {zone_id}: {e}")
        return False


# =========================
# PROCESADOR PRINCIPAL
# =========================

def process_symbol(symbol):
    """
    Procesa un símbolo: analiza SMC y gestiona zonas.
    
    Args:
        symbol: Símbolo del índice a procesar
    """
    print(f"\n🔍 Procesando {symbol}...")
    
    # 1. Obtener velas desde Supabase
    df_h1 = get_candles_from_supabase(symbol, "H1", CANDLES_BY_TIMEFRAME["H1"])
    df_m15 = get_candles_from_supabase(symbol, "M15", CANDLES_BY_TIMEFRAME["M15"])
    
    if df_h1.empty or df_m15.empty:
        print(f"  ⚠️  No hay suficientes datos para {symbol}")
        return
    
    # 2. Ejecutar análisis SMC_TENDENCY_H1_M15
    result = analyze_smc_tendency_h1_m15(symbol, df_h1, df_m15)
    
    zona = result.get('zona')
    es_valido = result.get('es_valido', False)
    razon_validacion = result.get('razon_validacion', '')
    
    print(f"  📊 Tendencia H1: {result['tendencia_h1']}")
    print(f"  📊 Tendencia M15: {result['tendencia_m15']} (informativa)")
    print(f"  🔍 Validación: {razon_validacion}")
    
    # 3. Si no hay zona o no es válida, terminar
    if not zona:
        print(f"  ℹ️  No hay zona M15 para {symbol}")
        return
    
    if not es_valido:
        print(f"  ⚠️  Zona NO válida para {symbol} - No se guarda")
        return
    
    # 4. Obtener zonas activas existentes
    active_zones = get_active_zones_for_symbol(symbol)
    
    # 5. Verificar si la zona ya existe (evitar duplicados)
    zona_min, zona_max = get_zone_boundaries(zona['zona_desde'], zona['zona_hasta'])
    
    for active_zone in active_zones:
        active_min, active_max = get_zone_boundaries(active_zone['zona_desde'], active_zone['zona_hasta'])
        
        # Si las zonas se solapan significativamente
        overlap_min = max(zona_min, active_min)
        overlap_max = min(zona_max, active_max)
        
        if overlap_max > overlap_min:
            overlap_size = overlap_max - overlap_min
            new_zone_size = zona_max - zona_min
            
            # Si el solapamiento es > 50% del tamaño de la nueva zona
            if overlap_size > new_zone_size * 0.5:
                print(f"  ℹ️  Zona similar ya existe (ID: {active_zone['id']}) - No se duplica")
                return
    
    # 6. Pausar zonas activas anteriores del mismo símbolo
    for active_zone in active_zones:
        pause_zone(active_zone['id'], "Reemplazada por nueva zona activa")
    
    # 7. Guardar nueva zona (solo si es válida)
    save_zone_to_supabase(symbol, result, zona)


def main_loop():
    """
    Loop principal del procesador SMC_TENDENCY_H1_M15.
    """
    print("\n" + "="*70)
    print(" SMC_TENDENCY_H1_M15 PROCESSOR")
    print("="*70)
    print(f"Tabla objetivo: {TARGET_TABLE}")
    print(f"Intervalo de procesamiento: {PROCESS_INTERVAL_SECONDS}s")
    print("="*70)
    
    iteration = 0
    
    while True:
        try:
            iteration += 1
            print(f"\n{'='*70}")
            print(f"Iteración #{iteration} - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
            print(f"{'='*70}")
            
            for symbol in SYMBOLS:
                try:
                    process_symbol(symbol)
                except Exception as e:
                    print(f"❌ Error procesando {symbol}: {e}")
            
            print(f"\n✅ Iteración #{iteration} completada")
            print(f"⏳ Esperando {PROCESS_INTERVAL_SECONDS}s hasta la próxima iteración...")
            
            time.sleep(PROCESS_INTERVAL_SECONDS)
        
        except KeyboardInterrupt:
            print("\n\n⏹️  Procesador detenido por el usuario")
            break
        except Exception as e:
            print(f"\n❌ Error en loop principal: {e}")
            print(f"⏳ Esperando {PROCESS_INTERVAL_SECONDS}s antes de reintentar...")
            time.sleep(PROCESS_INTERVAL_SECONDS)


if __name__ == "__main__":
    main_loop()
