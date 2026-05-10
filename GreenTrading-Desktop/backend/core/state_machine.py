#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GreenTrading Desktop - SMC M15 State Machine

Máquina de estados para SMC M15 PRO.

Contiene:
  - Constantes de configuración de la máquina de estados
  - Funciones de logging obligatorio (PRICE ENTERED ZONE CHECK,
    PROFIT_TRANSITION_CHECK)
  - Cálculo de velocidad M1 hacia la zona
  - Cálculo de estado dashboard (posición del precio)
  - Transiciones de estado validadas (máquina de estados completa)
"""

import pandas as pd

# =========================
# CONSTANTS
# =========================

M1_VELAS_ZONA = 15
LLEGANDO_A_ZONA_MINUTOS_UMBRAL = 5.0  # Tiempo estimado (min) para clasificar LLEGANDO_A_ZONA


# =========================
# LOGGING FUNCTIONS
# =========================

def log_price_entered_zone_check(
    symbol: str,
    precio_actual: float,
    entrada: float,
    stoploss: float,
    zona_desde: float,
    zona_hasta: float,
    direccion_operativa: str,
    en_zona_operativa: bool,
    estado_antes: str,
    estado_despues: str
) -> None:
    """Log obligatorio para validar prioridad de EN_ZONA."""
    print("\nPRICE ENTERED ZONE CHECK")
    print(f"  symbol: {symbol if symbol else '?'}")
    print(f"  precio_actual: {precio_actual}")
    print(f"  entrada: {entrada}")
    print(f"  stoploss: {stoploss}")
    print(f"  zona_desde: {zona_desde}")
    print(f"  zona_hasta: {zona_hasta}")
    print(f"  direccion_operativa: {direccion_operativa}")
    print(f"  en_zona_operativa: {en_zona_operativa}")
    print(f"  estado_antes: {estado_antes}")
    print(f"  estado_despues: {estado_despues}")


def log_profit_transition_check(
    symbol: str,
    estado_previo: str,
    precio_actual: float,
    entrada: float,
    stoploss: float,
    tp_1_1: float,
    direccion: str,
    en_zona: bool,
    salio_a_favor: bool,
    toco_tp: bool,
    toco_sl: bool,
    estado_final: str
) -> None:
    """Log obligatorio para EN_ZONA -> PROFIT -> TP/SL."""
    print("\nPROFIT_TRANSITION_CHECK")
    print(f"  symbol: {symbol if symbol else '?'}")
    print(f"  estado_previo: {estado_previo}")
    print(f"  precio_actual: {precio_actual}")
    print(f"  entrada: {entrada}")
    print(f"  stoploss: {stoploss}")
    print(f"  tp_1_1: {tp_1_1}")
    print(f"  direccion: {direccion}")
    print(f"  en_zona: {en_zona}")
    print(f"  salio_a_favor: {salio_a_favor}")
    print(f"  toco_tp: {toco_tp}")
    print(f"  toco_sl: {toco_sl}")
    print(f"  estado_final: {estado_final}")


# =========================
# VELOCITY
# =========================

def calcular_velocidad_m1_hacia_zona(df_m1, entrada, direccion, min_velas=3, lookback=None):
    """
    Calcula la velocidad promedio (puntos/minuto) de las velas M1 que avanzan hacia la zona.

    Para BOOM (ALCISTA): velas bajistas (close < open) empujan el precio hacia la entrada (abajo).
    Para CRASH (BAJISTA): velas alcistas (close > open) empujan el precio hacia la entrada (arriba).

    Args:
        df_m1: DataFrame de velas M1 (columnas: open, close, high, low)
        entrada: Precio de entrada de la zona
        direccion: "ALCISTA" o "BAJISTA"
        min_velas: Minimo de velas direccionales requeridas (defecto 3)
        lookback: Cuantas velas M1 recientes analizar (defecto M1_VELAS_ZONA)

    Returns:
        dict con:
            cantidad_velas: int  -- velas que avanzan hacia la zona
            velocidad: float     -- puntos por minuto promedio
            suficientes: bool    -- True si hay al menos min_velas
    """
    if lookback is None:
        lookback = M1_VELAS_ZONA

    if df_m1 is None or len(df_m1) == 0:
        return {"cantidad_velas": 0, "velocidad": 0.0, "suficientes": False}

    df_recent = df_m1.tail(lookback)

    if direccion == "ALCISTA":
        # BOOM: velas bajistas (close < open) empujan precio hacia la entrada (abajo)
        mask = df_recent["close"] < df_recent["open"]
        movimientos = (df_recent.loc[mask, "open"] - df_recent.loc[mask, "close"]).tolist()
    else:
        # CRASH: velas alcistas (close > open) empujan precio hacia la entrada (arriba)
        mask = df_recent["close"] > df_recent["open"]
        movimientos = (df_recent.loc[mask, "close"] - df_recent.loc[mask, "open"]).tolist()

    cantidad = len(movimientos)
    if cantidad < min_velas:
        return {"cantidad_velas": cantidad, "velocidad": 0.0, "suficientes": False}

    velocidad = sum(movimientos) / cantidad
    return {"cantidad_velas": cantidad, "velocidad": velocidad, "suficientes": True}


# =========================
# ESTADO DASHBOARD
# =========================

def calcular_estado_dashboard(
    precio_actual: float,
    entrada: float,
    zona_desde: float,
    zona_hasta: float,
    direccion: str,
    df_m1=None,
    symbol: str = ""
) -> str:
    """
    Calcula el estado del dashboard segun la posicion del precio.

    Reglas por direccion:

    BAJISTA (Crash):
        - entrada = zona_desde (borde inferior), stoploss = zona_hasta (borde superior)
        - El precio debe venir desde ABAJO para buscar la zona
        - Si precio > zona_hasta: SIN_SETUP (precio sobre stoploss, zona invalida)
        - Si zona_desde <= precio <= zona_hasta: EN_ZONA
        - Si precio < zona_desde: ACTIVA o LLEGANDO_A_ZONA segun velocidad M1
        - PROFIT: calculado solo por la maquina de estados (requiere haber pasado por EN_ZONA)

    ALCISTA (Boom):
        - entrada = zona_hasta (borde superior), stoploss = zona_desde (borde inferior)
        - El precio debe venir desde ARRIBA para buscar la zona
        - Si precio < zona_desde: SIN_SETUP (precio bajo stoploss, zona invalida)
        - Si zona_desde <= precio <= zona_hasta: EN_ZONA
        - Si precio > zona_hasta: ACTIVA o LLEGANDO_A_ZONA segun velocidad M1
        - PROFIT: calculado solo por la maquina de estados (requiere haber pasado por EN_ZONA)

    LLEGANDO_A_ZONA: se determina por velocidad M1 hacia la zona.
        distancia_a_entrada / velocidad_m1_hacia_zona <= 5 minutos => LLEGANDO_A_ZONA
        Si no hay suficientes velas M1 direccionales => ACTIVA (no inventar LLEGANDO_A_ZONA)

    Args:
        precio_actual: Precio actual
        entrada: Precio de entrada (zona_desde para Crash, zona_hasta para Boom)
        zona_desde: Limite inferior de zona
        zona_hasta: Limite superior de zona
        direccion: "ALCISTA" o "BAJISTA"
        df_m1: DataFrame de velas M1 recientes (opcional)
        symbol: Nombre del simbolo para logs (opcional)

    Returns:
        Estado dashboard: SIN_SETUP | EN_ZONA | ACTIVA | LLEGANDO_A_ZONA
    """
    # EN_ZONA tiene prioridad absoluta:
    # BOOM (ALCISTA): stoploss <= precio_actual <= entrada
    # CRASH (BAJISTA): entrada <= precio_actual <= stoploss
    if direccion == "ALCISTA":
        en_zona_operativa = zona_desde <= precio_actual <= entrada
    else:
        en_zona_operativa = entrada <= precio_actual <= zona_hasta

    estado_despues_check = "EN_ZONA" if en_zona_operativa else "CONTINUA_EVALUACION"
    log_price_entered_zone_check(
        symbol=symbol,
        precio_actual=precio_actual,
        entrada=entrada,
        stoploss=zona_desde if direccion == "ALCISTA" else zona_hasta,
        zona_desde=zona_desde,
        zona_hasta=zona_hasta,
        direccion_operativa=direccion,
        en_zona_operativa=en_zona_operativa,
        estado_antes="CALCULANDO_DASHBOARD",
        estado_despues=estado_despues_check
    )

    if en_zona_operativa:
        return "EN_ZONA"

    if direccion == "ALCISTA":
        # Boom: precio se acerca desde ARRIBA.
        # Si esta por debajo del stoploss (zona_desde), la zona es invalida.
        if precio_actual < zona_desde:
            return "SIN_SETUP"
        # precio_actual > zona_hasta: acercandose desde arriba
        distancia = precio_actual - zona_hasta
        stoploss_log = zona_desde
    else:
        # BAJISTA (Crash): precio se acerca desde ABAJO.
        # Si esta por encima del stoploss (zona_hasta), la zona es invalida.
        if precio_actual > zona_hasta:
            return "SIN_SETUP"
        # precio_actual < zona_desde: acercandose desde abajo
        distancia = zona_desde - precio_actual
        stoploss_log = zona_hasta

    # Clasificar usando velocidad M1 hacia la zona
    vel_result = calcular_velocidad_m1_hacia_zona(df_m1, entrada, direccion)
    cantidad_velas = vel_result["cantidad_velas"]
    velocidad = vel_result["velocidad"]
    suficientes = vel_result["suficientes"]

    if suficientes and velocidad > 0:
        tiempo_estimado = distancia / velocidad
        estado_resultado = "LLEGANDO_A_ZONA" if tiempo_estimado <= LLEGANDO_A_ZONA_MINUTOS_UMBRAL else "ACTIVA"
    else:
        tiempo_estimado = None
        estado_resultado = "ACTIVA"

    # Log requerido por especificacion
    sym_label = symbol if symbol else "?"
    print(f"\n--- LLEGANDO_A_ZONA EVAL [{sym_label}] ---")
    print(f"  precio_actual: {precio_actual}")
    print(f"  entrada: {entrada}")
    print(f"  stoploss: {stoploss_log}")
    print(f"  distancia_a_entrada: {round(distancia, 4)}")
    print(f"  cantidad_velas_m1_hacia_zona: {cantidad_velas}")
    print(f"  velocidad_m1_hacia_zona: {round(velocidad, 4)} pts/min")
    if tiempo_estimado is not None:
        print(f"  tiempo_estimado_min: {round(tiempo_estimado, 2)}")
    else:
        print(f"  tiempo_estimado_min: N/A (sin velas suficientes)")
    print(f"  estado_dashboard: {estado_resultado}")
    print(f"---------------------------------------------")

    return estado_resultado


# =========================
# STATE MACHINE
# =========================

def calcular_transicion_estado(
    symbol: str,
    estado_previo: str,
    estado_calculado: str,
    precio_actual: float,
    entrada: float,
    stoploss: float,
    tp: float,
    zona_desde: float,
    zona_hasta: float
) -> tuple:
    """
    Calcula la transición de estado válida basada en el estado previo.

    MÁQUINA DE ESTADOS CORRECTA:

    ESPERANDO_ENTRADA <-> LLEGANDO_A_ZONA (pueden oscilar)
    ESPERANDO_ENTRADA -> EN_ZONA
    LLEGANDO_A_ZONA -> EN_ZONA

    EN_ZONA -> PROFIT (salida favorable)
    EN_ZONA -> SL (toca stoploss)
    EN_ZONA -> EN_ZONA (se mantiene)

    PROFIT -> TP (alcanza 1:1)
    PROFIT -> SL (retrocede a stoploss)
    PROFIT -> EN_ZONA (precio vuelve a la zona)
    PROFIT -> PROFIT (se mantiene)

    TP, SL, DESCARTADA = terminales (no cambian)

    REGLA CLAVE:
    - Una vez EN_ZONA, NUNCA vuelve a: ESPERANDO_ENTRADA, LLEGANDO_A_ZONA, ACTIVA

    Args:
        symbol: Symbol name
        estado_previo: Estado guardado previamente (None si es nueva zona)
        estado_calculado: Estado calculado por lógica actual
        precio_actual: Precio actual
        entrada: Precio de entrada
        stoploss: Stop loss
        tp: Take profit 1:1
        zona_desde: Límite inferior de zona
        zona_hasta: Límite superior de zona

    Returns:
        tuple (estado_final, motivo_transicion)
    """
    direccion = "ALCISTA" if entrada > stoploss else "BAJISTA"
    en_zona_operativa = (
        (direccion == "ALCISTA" and stoploss <= precio_actual <= entrada) or
        (direccion == "BAJISTA" and entrada <= precio_actual <= stoploss)
    )
    salio_a_favor = (
        (direccion == "ALCISTA" and precio_actual > entrada) or
        (direccion == "BAJISTA" and precio_actual < entrada)
    )
    toco_tp = (
        (direccion == "ALCISTA" and precio_actual >= tp) or
        (direccion == "BAJISTA" and precio_actual <= tp)
    )
    toco_sl = (
        (direccion == "ALCISTA" and precio_actual <= stoploss) or
        (direccion == "BAJISTA" and precio_actual >= stoploss)
    )

    estado_antes_check = estado_previo if estado_previo else estado_calculado
    estado_despues_check = "EN_ZONA" if en_zona_operativa else estado_calculado
    log_price_entered_zone_check(
        symbol=symbol,
        precio_actual=precio_actual,
        entrada=entrada,
        stoploss=stoploss,
        zona_desde=zona_desde,
        zona_hasta=zona_hasta,
        direccion_operativa=direccion,
        en_zona_operativa=en_zona_operativa,
        estado_antes=estado_antes_check,
        estado_despues=estado_despues_check
    )

    def finalizar(estado_final: str, motivo: str) -> tuple:
        log_profit_transition_check(
            symbol=symbol,
            estado_previo=estado_previo,
            precio_actual=precio_actual,
            entrada=entrada,
            stoploss=stoploss,
            tp_1_1=tp,
            direccion=direccion,
            en_zona=en_zona_operativa,
            salio_a_favor=salio_a_favor,
            toco_tp=toco_tp,
            toco_sl=toco_sl,
            estado_final=estado_final
        )
        return estado_final, motivo

    # CHECK 1: Si NO hay estado previo, solo permitir ACTIVA/ESPERANDO_ENTRADA
    if not estado_previo:
        if estado_calculado == 'SIN_SETUP':
            return finalizar("SIN_SETUP", "Zona invalida: precio fuera del rango valido para esta direccion")
        if en_zona_operativa:
            return finalizar("EN_ZONA", "Nueva zona detectada (precio dentro de zona)")
        if toco_tp:
            return finalizar("ACTIVA", "Nueva zona detectada (precio en TP, requiere monitoreo)")
        elif toco_sl:
            return finalizar("ACTIVA", "Nueva zona detectada (precio en SL, requiere monitoreo)")
        elif estado_calculado in ['ACTIVA', 'ESPERANDO_ENTRADA', 'LLEGANDO_A_ZONA']:
            return finalizar(estado_calculado, "Nueva zona detectada")
        elif estado_calculado == 'EN_ZONA':
            return finalizar("ACTIVA", "Nueva zona detectada (calculado EN_ZONA, sin historial previo)")
        elif estado_calculado == 'PROFIT':
            return finalizar("ACTIVA", "Nueva zona detectada (precio en profit, sin historial previo)")
        else:
            return finalizar("ACTIVA", "Nueva zona detectada")

    if estado_previo in ['TP', 'SL']:
        return finalizar(estado_previo, f"Estado terminal {estado_previo} (no cambia)")

    if estado_previo == 'PROFIT':
        if toco_tp:
            return finalizar("TP", "Take Profit alcanzado")
        if toco_sl:
            return finalizar("SL", "Stop Loss alcanzado")
        if en_zona_operativa:
            return finalizar("EN_ZONA", "Precio volvio a la zona")
        return finalizar("PROFIT", "Mantiene profit (esperando TP o SL)")

    if estado_previo == 'EN_ZONA':
        if toco_sl:
            return finalizar("SL", "Stop Loss alcanzado")
        if toco_tp:
            return finalizar("TP", "Take Profit alcanzado")
        if salio_a_favor:
            return finalizar("PROFIT", "Precio salio en direccion favorable")
        if en_zona_operativa:
            return finalizar("EN_ZONA", "Precio sigue en zona")
        return finalizar("EN_ZONA", "Zona mantiene memoria (sin regreso a estados previos)")

    if estado_previo in ['ACTIVA', 'ESPERANDO_ENTRADA', 'LLEGANDO_A_ZONA']:
        if en_zona_operativa or estado_calculado == 'EN_ZONA':
            log_price_entered_zone_check(
                symbol=symbol,
                precio_actual=precio_actual,
                entrada=entrada,
                stoploss=stoploss,
                zona_desde=zona_desde,
                zona_hasta=zona_hasta,
                direccion_operativa=direccion,
                en_zona_operativa=en_zona_operativa,
                estado_antes=estado_previo,
                estado_despues="EN_ZONA"
            )
            return finalizar("EN_ZONA", "Precio tocó la zona")
        elif estado_calculado == 'PROFIT':
            return finalizar(estado_previo, f"Mantiene {estado_previo} (no puede saltar a PROFIT sin pasar por EN_ZONA)")
        elif toco_sl:
            return finalizar(estado_previo, f"Mantiene {estado_previo} (sin cierre por SL antes de EN_ZONA)")
        else:
            return finalizar(estado_calculado, f"Transición desde {estado_previo}")

    if toco_sl:
        return finalizar("SL", "Stop Loss alcanzado")

    return finalizar(estado_calculado, f"Transición estándar desde {estado_previo}")


def calcular_estado_historial(
    symbol: str,
    estado_dashboard: str,
    precio_actual: float,
    entrada: float,
    stoploss: float,
    tp: float,
    zona_desde: float,
    zona_hasta: float,
    estado_previo: str = None
) -> tuple:
    """
    Calcula estado historial validando transiciones correctas.

    CORRECCIÓN CRÍTICA: Ahora usa estado previo guardado para validar
    que las transiciones sean correctas según la máquina de estados.

    Estados historial:
    - ACTIVA/ESPERANDO_ENTRADA: Estados iniciales para nuevas zonas
    - LLEGANDO_A_ZONA: Acercándose a zona
    - EN_ZONA: En zona (solo si antes estuvo ACTIVA)
    - PROFIT: En ganancia flotante (solo si antes estuvo EN_ZONA)
    - TP: Take profit alcanzado (solo si antes estuvo EN_ZONA o PROFIT)
    - SL: Stop loss alcanzado (solo si antes estuvo ACTIVA o EN_ZONA)

    Args:
        symbol: Symbol name
        estado_dashboard: Estado calculado por lógica de distancia
        precio_actual: Precio actual
        entrada: Precio de entrada
        stoploss: Stop loss
        tp: Take profit 1:1
        zona_desde: Límite inferior de zona
        zona_hasta: Límite superior de zona
        estado_previo: Estado guardado previamente en Supabase (None si nueva zona)

    Returns:
        tuple (estado_final, motivo_transicion)
    """
    # Calcular estado según lógica de precios
    estado_calculado = estado_dashboard

    # Calcular transición válida
    estado_final, motivo = calcular_transicion_estado(
        symbol,
        estado_previo,
        estado_calculado,
        precio_actual,
        entrada,
        stoploss,
        tp,
        zona_desde,
        zona_hasta
    )

    return estado_final, motivo
