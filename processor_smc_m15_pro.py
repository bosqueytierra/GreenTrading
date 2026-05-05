#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SMC M15 PRO - Procesador Backend

Este procesador:
1. Lee velas desde public.market_candles
2. Ejecuta análisis SMC M15 PRO (sin validación H1)
3. Guarda resultados SOLO en public.smc_m15_setups

IMPORTANTE:
- NO depende del dashboard abierto
- Corre independientemente cada 1 minuto
- Solo procesa y actualiza zonas
- Frontend SOLO lee y visualiza
"""

import os
import sys
import pandas as pd
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv
from src.smc_engine import analyze_smc

# Cargar variables de entorno
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

# ⚠️ TABLA OBLIGATORIA - NO MODIFICAR
# Esta estrategia SOLO usa smc_m15_setups
TARGET_TABLE = "smc_m15_setups"

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
    Calcula el tamaño de la zona en puntos.
    
    Args:
        zona_desde: Límite inferior o superior de la zona
        zona_hasta: Límite superior o inferior de la zona
    
    Returns:
        Tamaño de la zona (siempre positivo)
    """
    return abs(zona_hasta - zona_desde)


def calculate_tp_sl_prices(zona, direccion):
    """
    Calcula precios TP y SL con ratio 1:1.
    
    Args:
        zona: Diccionario con 'zona_desde' y 'zona_hasta'
        direccion: "ALCISTA" o "BAJISTA"
    
    Returns:
        Tupla (precio_entrada, sl_price, tp_price)
    """
    zona_desde = zona['zona_desde']
    zona_hasta = zona['zona_hasta']
    zona_size = calculate_zone_size(zona_desde, zona_hasta)
    
    if direccion == "ALCISTA":
        precio_entrada = zona_hasta
        sl_price = zona_desde
        tp_price = zona_hasta + zona_size
    else:  # BAJISTA
        precio_entrada = zona_desde
        sl_price = zona_hasta
        tp_price = zona_desde - zona_size
    
    return precio_entrada, sl_price, tp_price


# =========================
# SUPABASE DATA ACCESS
# =========================

def get_candles_from_supabase(symbol, timeframe, limit=500):
    """
    Obtiene velas desde public.market_candles.
    
    Args:
        symbol: Símbolo del índice
        timeframe: Timeframe (H1, M15, M1)
        limit: Número máximo de velas a obtener
    
    Returns:
        DataFrame con las velas o DataFrame vacío si hay error
    """
    url = (
        f"{SUPABASE_URL}/rest/v1/market_candles"
        f"?symbol=eq.{symbol}"
        f"&timeframe=eq.{timeframe}"
        f"&order=timestamp.desc"
        f"&limit={limit}"
    )
    
    try:
        response = requests.get(url, headers=supabase_headers(), timeout=15)
        
        if response.status_code != 200:
            print(f"❌ Error HTTP {response.status_code} obteniendo velas {symbol} {timeframe}")
            return pd.DataFrame()
        
        data = response.json()
        
        if not data:
            print(f"⚠️  No hay datos para {symbol} {timeframe}")
            return pd.DataFrame()
        
        # Convertir a DataFrame
        df = pd.DataFrame(data)
        
        # Ordenar por timestamp ascendente (más antiguo primero)
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        # Convertir timestamp a datetime
        df['time'] = pd.to_datetime(df['timestamp'])
        
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
    
    ⚠️ Lee SOLO de smc_m15_setups (estrategia SMC_M15_PRO)
    
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
    
    ⚠️ Actualiza SOLO en smc_m15_setups (estrategia SMC_M15_PRO)
    
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
    Guarda una zona en public.smc_m15_setups.
    
    ⚠️ Inserta SOLO en smc_m15_setups
    ⚠️ NUNCA insertar en smc_h1_m15_setups ni smc_tendency_h1_m15_setups
    
    Args:
        symbol: Símbolo del índice
        result: Resultado del análisis SMC
        zona: Zona depurada M15
    
    Returns:
        True si se guardó exitosamente, False si no
    """
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
        "tendencia_m15": result['tendencia_m15'],
        "strategy": "SMC_M15_PRO"
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


def update_zone_state(zone_id, estado, precio_actual, motivo_cierre=None):
    """
    Actualiza el estado de una zona existente.
    
    Args:
        zone_id: ID de la zona
        estado: Nuevo estado
        precio_actual: Precio actual
        motivo_cierre: Motivo de cierre (opcional)
    """
    url = f"{SUPABASE_URL}/rest/v1/{TARGET_TABLE}?id=eq.{zone_id}"
    
    data = {
        "estado": estado,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    if motivo_cierre:
        data["motivo_cierre"] = motivo_cierre
        data["fecha_cierre"] = datetime.now(timezone.utc).isoformat()
    
    try:
        response = requests.patch(url, headers=supabase_headers(), json=data, timeout=15)
        
        if response.status_code in [200, 204]:
            print(f"  📊 Zona {zone_id} actualizada a {estado}")
            return True
        
        print(f"  ❌ Error actualizando zona {zone_id}: {response.status_code}")
        return False
    
    except Exception as e:
        print(f"  ❌ Error actualizando zona {zone_id}: {e}")
        return False


# =========================
# CORE PROCESSING
# =========================

def process_symbol(symbol):
    """
    Procesa un símbolo: analiza SMC M15 PRO y actualiza zonas.
    
    Args:
        symbol: Símbolo del índice
    """
    print(f"\n{'─'*70}")
    print(f"📊 Procesando: {symbol}")
    print(f"{'─'*70}")
    
    # 1. Obtener velas desde Supabase
    df_h1 = get_candles_from_supabase(symbol, "H1", CANDLES_BY_TIMEFRAME["H1"])
    df_m15 = get_candles_from_supabase(symbol, "M15", CANDLES_BY_TIMEFRAME["M15"])
    
    if df_h1.empty or df_m15.empty:
        print(f"  ⚠️  No hay suficientes velas para {symbol}")
        return
    
    # Opcional: obtener M1 si se usa refinamiento
    df_m1 = None
    # df_m1 = get_candles_from_supabase(symbol, "M1", CANDLES_BY_TIMEFRAME["M1"])
    
    # 2. Ejecutar análisis SMC M15 PRO (sin validación H1)
    result = analyze_smc(df_h1, df_m15, df_m1)
    
    tendencia_h1 = result["tendencia_h1"]
    tendencia_m15 = result["tendencia_m15"]
    zona = result["zona"]
    precio_actual = result["precio_actual"]
    
    print(f"  Tendencia H1: {tendencia_h1}, M15: {tendencia_m15}")
    print(f"  Precio actual: {round(precio_actual, 3) if precio_actual else 'N/A'}")
    
    # 3. Si no hay zona, solo actualizar estados de zonas existentes
    if not zona:
        print(f"  ℹ️  No hay zona M15 para {symbol}")
        update_active_zones_states(symbol, precio_actual)
        return
    
    print(f"  Zona detectada: {zona['direccion']} | Score: {zona['score']}")
    
    # 4. Obtener zonas activas para este símbolo
    zonas_activas = get_active_zones_for_symbol(symbol)
    
    # 5. Verificar si ya existe una zona similar (misma dirección, rango similar)
    zona_existe = False
    for z in zonas_activas:
        # Verificar si es la misma dirección y rango similar
        if (z['direccion'] == zona['direccion'] and
            abs(z['zona_desde'] - zona['zona_desde']) < ZONE_SIMILARITY_THRESHOLD and
            abs(z['zona_hasta'] - zona['zona_hasta']) < ZONE_SIMILARITY_THRESHOLD):
            zona_existe = True
            print(f"  ℹ️  Zona similar ya existe (ID: {z['id']})")
            break
    
    if zona_existe:
        # Actualizar estados de zonas existentes
        update_active_zones_states(symbol, precio_actual)
        return
    
    # 6. Si hay zona nueva, pausar zonas activas anteriores
    if zonas_activas:
        print(f"  ⏸️  Pausando {len(zonas_activas)} zona(s) activa(s)...")
        for z in zonas_activas:
            pause_zone(z['id'], "Pausada por nueva zona activa")
    
    # 7. Guardar nueva zona
    save_zone_to_supabase(symbol, result, zona)
    
    # 8. Actualizar estados de zonas activas según precio actual
    update_active_zones_states(symbol, precio_actual)


def update_active_zones_states(symbol, precio_actual):
    """
    Actualiza estados de zonas activas según el precio actual.
    
    Args:
        symbol: Símbolo del índice
        precio_actual: Precio actual
    """
    # Obtener todas las zonas en estados activos (ACTIVA, EN_ZONA, PROFIT, PAUSADA)
    url = (
        f"{SUPABASE_URL}/rest/v1/{TARGET_TABLE}"
        f"?symbol=eq.{symbol}"
        f"&estado=in.(ACTIVA,EN_ZONA,PROFIT,PAUSADA)"
        f"&select=*"
    )
    
    try:
        response = requests.get(url, headers=supabase_headers(), timeout=15)
        
        if response.status_code != 200:
            return
        
        zonas = response.json()
        
        for zona in zonas:
            zone_id = zona['id']
            direccion = zona['direccion']
            zona_desde = zona['zona_desde']
            zona_hasta = zona['zona_hasta']
            tp_price = zona['tp_price']
            sl_price = zona['sl_price']
            estado_actual = zona['estado']
            
            # Calcular límites de zona usando helper
            zona_min, zona_max = get_zone_boundaries(zona_desde, zona_hasta)
            
            # Verificar SL primero (aplica a todos los estados)
            if direccion == "ALCISTA" and precio_actual <= sl_price:
                if estado_actual == "PAUSADA":
                    update_zone_state(zone_id, "SL", precio_actual, "Stop Loss alcanzado en zona pausada")
                else:
                    update_zone_state(zone_id, "SL", precio_actual, "SL alcanzado")
                continue
            
            elif direccion == "BAJISTA" and precio_actual >= sl_price:
                if estado_actual == "PAUSADA":
                    update_zone_state(zone_id, "SL", precio_actual, "Stop Loss alcanzado en zona pausada")
                else:
                    update_zone_state(zone_id, "SL", precio_actual, "SL alcanzado")
                continue
            
            # Para zonas PAUSADA, solo verificamos SL (ya verificado arriba)
            # NO reevaluamos por H1/M15 cambios en SMC_M15_PRO
            if estado_actual == "PAUSADA":
                continue
            
            # Verificar si precio está EN_ZONA
            if zona_min <= precio_actual <= zona_max:
                if estado_actual == "ACTIVA":
                    update_zone_state(zone_id, "EN_ZONA", precio_actual)
            
            # Verificar TP
            elif direccion == "ALCISTA" and precio_actual >= tp_price:
                update_zone_state(zone_id, "TP", precio_actual, "TP alcanzado")
            
            elif direccion == "BAJISTA" and precio_actual <= tp_price:
                update_zone_state(zone_id, "TP", precio_actual, "TP alcanzado")
            
            # Verificar PROFIT (salió de zona favorablemente pero no llegó a TP)
            elif estado_actual == "EN_ZONA":
                if (direccion == "ALCISTA" and precio_actual > zona_max) or \
                   (direccion == "BAJISTA" and precio_actual < zona_min):
                    update_zone_state(zone_id, "PROFIT", precio_actual, "Salió de zona en profit")
    
    except Exception as e:
        print(f"❌ Error actualizando estados de zonas para {symbol}: {e}")


def process_all_symbols():
    """Procesa todos los símbolos una vez"""
    print(f"\n{'='*70}")
    print(f" Procesando {len(SYMBOLS)} símbolos - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}")
    
    for symbol in SYMBOLS:
        try:
            process_symbol(symbol)
        except Exception as e:
            print(f"❌ Error procesando {symbol}: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n✅ Procesamiento completado")


if __name__ == "__main__":
    print("="*70)
    print(" SMC M15 PRO - Procesador Backend")
    print("="*70)
    print(f"⚠️  TABLA DESTINO: {TARGET_TABLE}")
    print(f"⚠️  NO escribe en: smc_h1_m15_setups ni smc_tendency_h1_m15_setups")
    print(f"Leyendo velas desde: public.market_candles")
    print(f"Guardando resultados en: public.{TARGET_TABLE}")
    print("="*70)
    
    try:
        process_all_symbols()
    except KeyboardInterrupt:
        print("\n\n👋 Procesador detenido por usuario")
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
