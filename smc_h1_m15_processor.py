#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SMC PRO TENDENCIA H1 + CHOCH/BOS (M15) - Procesador de Supabase

Este procesador:
1. Lee velas desde public.market_candles (misma fuente que SMC M15 PRO)
2. Ejecuta análisis SMC con validación H1 + M15
3. Guarda resultados en public.smc_h1_m15_setups

⚠️ IMPORTANTE - TABLA OBLIGATORIA:
   Este procesador SOLO debe escribir en: public.smc_h1_m15_setups
   NUNCA debe escribir en: public.smc_m15_setups (reservada para SMC M15 PRO)

NO crea nuevo collector MT5.
NO duplica velas.
Es otro consumidor de las mismas velas existentes.
"""

import os
import sys
import time
import pandas as pd
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv
from src.smc_engine_h1_m15 import analyze_smc_h1_m15

# Cargar variables de entorno
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

# ⚠️ TABLA OBLIGATORIA - NO MODIFICAR
# Esta estrategia SOLO usa smc_h1_m15_setups
# SMC M15 PRO usa smc_m15_setups (tabla diferente)
TARGET_TABLE = "smc_h1_m15_setups"

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
TERMINAL_STATES = {"TP", "SL", "PROFIT", "PAUSADA", "DESCARTADA"}

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
    
    ⚠️ Lee SOLO de smc_h1_m15_setups (estrategia H1+M15)
    
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


def get_all_zones_for_symbol(symbol):
    """
    Obtiene TODAS las zonas para un símbolo específico (incluyendo cerradas y descartadas).
    
    ⚠️ Lee SOLO de smc_h1_m15_setups (estrategia H1+M15)
    
    Args:
        symbol: Símbolo del índice
    
    Returns:
        Lista de todas las zonas
    """
    url = (
        f"{SUPABASE_URL}/rest/v1/{TARGET_TABLE}"
        f"?symbol=eq.{symbol}"
        f"&select=*"
        f"&order=created_at.desc"
    )
    
    try:
        response = requests.get(url, headers=supabase_headers(), timeout=15)
        
        if response.status_code == 200:
            return response.json()
        
        return []
    
    except Exception as e:
        print(f"❌ Error obteniendo todas las zonas para {symbol}: {e}")
        return []


def pause_zone(zone_id, motivo="Pausada por nueva zona activa"):
    """
    Pausa una zona existente.
    
    ⚠️ Actualiza SOLO en smc_h1_m15_setups (estrategia H1+M15)
    
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
    Guarda una zona en public.smc_h1_m15_setups.
    
    ⚠️ Inserta SOLO en smc_h1_m15_setups (estrategia H1+M15)
    ⚠️ NUNCA insertar en smc_m15_setups (estrategia SMC M15 PRO)
    
    Args:
        symbol: Símbolo del índice
        result: Resultado del análisis SMC
        zona: Zona depurada M15
    """
    tipo_indice = "Boom" if "Boom" in symbol else "Crash"
    
    # Determinar estado inicial
    if result['es_valido']:
        estado = "ACTIVA"
        motivo_cierre = None
    else:
        estado = "DESCARTADA"
        motivo_cierre = result['razon_validacion']
    
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
        "estado": estado,
        "tp_price": tp_price,
        "sl_price": sl_price,
        "ratio_rr": 1.0,
        "max_reaccion_puntos": 0.0,
        "resultado_puntos": None,
        "fecha_cierre": datetime.now(timezone.utc).isoformat() if estado == "DESCARTADA" else None,
        "motivo_cierre": motivo_cierre,
        "tendencia_h1": result['tendencia_h1'],
        "tendencia_m15": result['tendencia_m15'],
        "estrategia": "SMC PRO TENDENCIA H1 + CHOCH/BOS (M15)"
    }
    
    url = f"{SUPABASE_URL}/rest/v1/{TARGET_TABLE}"
    
    try:
        response = requests.post(url, headers=supabase_headers(), json=data, timeout=15)
        
        if response.status_code in [200, 201]:
            print(f"  ✅ Zona guardada: {symbol} {zona['direccion']} ({estado})")
            return True
        
        print(f"  ❌ Error guardando zona {symbol}: {response.status_code} - {response.text}")
        return False
    
    except Exception as e:
        print(f"  ❌ Error guardando zona {symbol}: {e}")
        return False


def update_zone_state(zone_id, new_state, precio_actual, motivo=None):
    """
    Actualiza el estado de una zona.
    
    ⚠️ Actualiza SOLO en smc_h1_m15_setups (estrategia H1+M15)
    
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
        print(f"  ⚠️  No hay suficientes velas para {symbol}")
        return
    
    # Opcional: obtener M1 si se usa refinamiento
    df_m1 = None
    # df_m1 = get_candles_from_supabase(symbol, "M1", CANDLES_BY_TIMEFRAME["M1"])
    
    # 2. Ejecutar análisis SMC con validación H1 + M15
    result = analyze_smc_h1_m15(symbol, df_h1, df_m15, df_m1)
    
    tendencia_h1 = result["tendencia_h1"]
    tendencia_m15 = result["tendencia_m15"]
    zona = result["zona"]
    precio_actual = result["precio_actual"]
    es_valido = result["es_valido"]
    razon_validacion = result["razon_validacion"]
    
    print(f"  Tendencia H1: {tendencia_h1}, M15: {tendencia_m15}")
    print(f"  Precio actual: {round(precio_actual, 3) if precio_actual else 'N/A'}")
    
    # 3. Si no hay zona, terminar
    if not zona:
        print(f"  ℹ️  No hay zona M15 para {symbol}")
        return
    
    print(f"  Zona detectada: {zona['direccion']} | Score: {zona['score']}")
    print(f"  Validación H1+M15: {'✅ VÁLIDO' if es_valido else '❌ DESCARTADO'} - {razon_validacion}")
    
    # 4. Obtener TODAS las zonas para este símbolo (para detectar duplicados exactos)
    todas_zonas = get_all_zones_for_symbol(symbol)
    
    # 5. Verificar si ya existe una zona EXACTA (symbol + zona_desde + zona_hasta + evento)
    # Tolerancia para comparación de floats
    tolerance = 0.001
    zona_duplicada = None
    ultimo_evento = zona['evento']['evento']
    
    for z in todas_zonas:
        zona_desde_match = abs(z['zona_desde'] - zona['zona_desde']) < tolerance
        zona_hasta_match = abs(z['zona_hasta'] - zona['zona_hasta']) < tolerance
        evento_match = z['evento'] == ultimo_evento
        
        if zona_desde_match and zona_hasta_match and evento_match:
            zona_duplicada = z
            print(f"  ℹ️  Zona duplicada encontrada (ID: {z['id']}, estado: {z['estado']})")
            break
    
    # 6. Si encontramos una zona duplicada, UPDATE en lugar de INSERT
    if zona_duplicada:
        # Calcular nuevo estado según validación y estado de dashboard
        zonas_activas = get_active_zones_for_symbol(symbol)
        
        # Determinar si hay dashboard lock
        dashboard_locked = any(
            zact['estado'] in ['EN_ZONA', 'PROFIT', 'TP'] 
            for zact in zonas_activas
        )
        
        # Determinar nuevo estado
        if not es_valido:
            nuevo_estado = 'DESCARTADA'
            fecha_cierre = datetime.now(timezone.utc).isoformat()
            motivo_cierre = razon_validacion
        elif zona_duplicada['estado'] in ['DESCARTADA', 'SL', 'TP'] and zona_duplicada.get('fecha_cierre'):
            # Reactivar zona que estaba cerrada
            nuevo_estado = 'PAUSADA' if dashboard_locked else 'ACTIVA'
            fecha_cierre = None
            motivo_cierre = None
            print(f"  🔄 Reactivando zona desde {zona_duplicada['estado']} → {nuevo_estado}")
        else:
            # Zona en otros estados (ACTIVA, PAUSADA, EN_ZONA, PROFIT, etc.): mantener estado actual
            nuevo_estado = zona_duplicada['estado']
            fecha_cierre = zona_duplicada.get('fecha_cierre')
            motivo_cierre = zona_duplicada.get('motivo_cierre')
        
        # UPDATE la zona duplicada
        update_data = {
            "estado": nuevo_estado,
            "score": zona['score'],
            "ob": bool(zona['ob']),
            "fvg": bool(zona['fvg']),
            "barrida": bool(zona['barrida']),
            "tendencia_h1": tendencia_h1,
            "tendencia_m15": tendencia_m15,
            "fecha_cierre": fecha_cierre,
            "motivo_cierre": motivo_cierre
        }
        
        url = f"{SUPABASE_URL}/rest/v1/{TARGET_TABLE}?id=eq.{zona_duplicada['id']}"
        
        try:
            response = requests.patch(url, headers=supabase_headers(), json=update_data, timeout=15)
            
            if response.status_code in [200, 204]:
                print(f"  ✅ Zona duplicada actualizada: ID {zona_duplicada['id']} → estado: {nuevo_estado}")
            else:
                print(f"  ❌ Error actualizando zona duplicada: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"  ❌ Error actualizando zona duplicada: {e}")
        
        return
    
    # 7. Si no hay duplicado exacto, verificar zonas activas para pausar
    zonas_activas = get_active_zones_for_symbol(symbol)
    if es_valido and zonas_activas:
        print(f"  ⏸️  Pausando {len(zonas_activas)} zona(s) activa(s)...")
        for z in zonas_activas:
            pause_zone(z['id'], "Pausada por nueva zona activa")
    
    # 8. Guardar nueva zona (válida o descartada)
    save_zone_to_supabase(symbol, result, zona)
    
    # 9. Actualizar estados de zonas activas según precio actual
    # (Esto se podría hacer en un procesador separado que corre más frecuentemente)
    update_active_zones_states(symbol, precio_actual)


def update_active_zones_states(symbol, precio_actual):
    """
    Actualiza estados de zonas activas según el precio actual.
    
    Args:
        symbol: Símbolo del índice
        precio_actual: Precio actual
    """
    zonas_activas = get_active_zones_for_symbol(symbol)
    
    for zona in zonas_activas:
        zone_id = zona['id']
        direccion = zona['direccion']
        zona_desde = zona['zona_desde']
        zona_hasta = zona['zona_hasta']
        tp_price = zona['tp_price']
        sl_price = zona['sl_price']
        estado_actual = zona['estado']
        
        # Calcular límites de zona usando helper
        zona_min, zona_max = get_zone_boundaries(zona_desde, zona_hasta)
        
        # Verificar si precio está EN_ZONA
        if zona_min <= precio_actual <= zona_max:
            if estado_actual == "ACTIVA":
                update_zone_state(zone_id, "EN_ZONA", precio_actual)
        
        # Verificar TP
        elif direccion == "ALCISTA" and precio_actual >= tp_price:
            update_zone_state(zone_id, "TP", precio_actual, "TP alcanzado")
        
        elif direccion == "BAJISTA" and precio_actual <= tp_price:
            update_zone_state(zone_id, "TP", precio_actual, "TP alcanzado")
        
        # Verificar SL
        elif direccion == "ALCISTA" and precio_actual <= sl_price:
            update_zone_state(zone_id, "SL", precio_actual, "SL alcanzado")
        
        elif direccion == "BAJISTA" and precio_actual >= sl_price:
            update_zone_state(zone_id, "SL", precio_actual, "SL alcanzado")
        
        # Verificar PROFIT (salió de zona favorablemente pero no llegó a TP)
        elif estado_actual == "EN_ZONA":
            if (direccion == "ALCISTA" and precio_actual > zona_max) or \
               (direccion == "BAJISTA" and precio_actual < zona_min):
                update_zone_state(zone_id, "PROFIT", precio_actual, "Salió de zona en profit")


def main():
    """Loop principal del procesador"""
    print("="*70)
    print(" SMC PRO TENDENCIA H1 + CHOCH/BOS (M15) - Procesador")
    print("="*70)
    print(f"⚠️  TABLA DESTINO: {TARGET_TABLE}")
    print(f"⚠️  NO escribe en: smc_m15_setups (tabla de SMC M15 PRO)")
    print(f"Procesando {len(SYMBOLS)} símbolos cada {PROCESS_INTERVAL_SECONDS}s")
    print(f"Leyendo velas desde: public.market_candles")
    print(f"Guardando resultados en: public.{TARGET_TABLE}")
    print("="*70)
    
    ciclo = 0
    
    while True:
        ciclo += 1
        print(f"\n{'='*70}")
        print(f" Ciclo #{ciclo} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}")
        
        for symbol in SYMBOLS:
            try:
                process_symbol(symbol)
            except Exception as e:
                print(f"❌ Error procesando {symbol}: {e}")
                import traceback
                traceback.print_exc()
        
        print(f"\n✅ Ciclo #{ciclo} completado")
        print(f"⏰ Próximo ciclo en {PROCESS_INTERVAL_SECONDS} segundos...")
        
        time.sleep(PROCESS_INTERVAL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Procesador detenido por usuario")
        sys.exit(0)
