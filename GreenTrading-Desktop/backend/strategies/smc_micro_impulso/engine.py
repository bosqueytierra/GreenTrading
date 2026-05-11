#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SMC MICRO IMPULSO strategy engine.

Estrategia agresiva 100% basada en micro estructura M1.

Diferencias clave vs SMC_M15_PRO y SMC_H1_M15_PRO:
  - H1: NO se usa.
  - M15: solo contexto informativo opcional, NO bloquea setups.
  - M1: núcleo operativo completo (swings, BOS/CHOCH, barrida, OB, FVG, zona).
  - TP ratio 1:1 (guardado en campo tp_1_1).
  - strategy_id = "SMC_MICRO_IMPULSO" — completamente aislado.
  - PRE-ZONA revalida cada ciclo; POST-ZONA no invalida trade vivo.
"""

import traceback
from datetime import datetime, timezone

import pandas as pd

from core.state_machine import (
    log_price_entered_zone_check,
    calcular_estado_dashboard,
    calcular_estado_historial,
)
from strategies.base_strategy import BaseStrategy
from strategies.smc_m15_pro.engine import (
    direccion_operativa_por_indice,
    validar_zona_operativa,
    detectar_swings,
    detectar_estructura,
    detectar_fvg,
    buscar_order_block,
    detectar_barrida_previa,
    format_trend,
    get_last_event,
)

STRATEGY_ID = "SMC_MICRO_IMPULSO"
STRATEGY_NAME = "SMC MICRO IMPULSO"
TP_RATIO = 1.0

# M1-specific lookback: smaller because M1 swings are shorter and more frequent.
SWING_LOOKBACK_M1 = 2
# Maximum age of last M1 structural event before context is considered stale.
MAX_EVENTO_STALENESS_M1 = 50  # velas M1 (~50 min)
# Minimum number of candles in the impulsive displacement window.
DESPLAZAMIENTO_VENTANA = 5
# Minimum directional candles required for a valid displacement.
DESPLAZAMIENTO_MIN_VELAS = 3
# Minimum zone size in price points; zones smaller than this are rejected.
MIN_ZONA_SIZE = 1.0
# Lookback for local M1 sweep detection (fewer candles than M15).
BARRIDA_LOOKBACK_M1 = 20


# =============================================================================
# SIN SETUP RESPONSE
# =============================================================================

def create_sin_setup_micro_impulso_response(
    symbol: str,
    price: float = None,
    tendencia_m15: str = "--",
    ultimo_evento_m1: str = "--",
    estado_dashboard: str = "SIN_SETUP",
) -> dict:
    """
    Crea respuesta mínima SIN SETUP para SMC_MICRO_IMPULSO.

    Todos los paths SIN_SETUP retornan estado_dashboard, estado_historial y
    estado_final seteados al mismo valor (convención del proyecto).

    Args:
        symbol: Symbol name.
        price: Current price (optional).
        tendencia_m15: M15 trend (informational only).
        ultimo_evento_m1: Last M1 structural event (informational).
        estado_dashboard: Dashboard state string.

    Returns:
        dict compatible with snapshot shape.
    """
    return {
        "symbol": symbol,
        "price": price,
        "tendencia_m15": tendencia_m15,
        "ultimo_evento_m1": ultimo_evento_m1,
        "zona_madre_m1": {"desde": 0, "hasta": 0},
        "entrada": None,
        "stoploss": None,
        "tp_1_1": None,
        "tp_ratio": TP_RATIO,
        "score": 0,
        "ob": "NO",
        "fvg": "NO",
        "barrida": "NO",
        "desplazamiento_valido": "NO",
        "micro_bos_choch": "--",
        "estado_dashboard": estado_dashboard,
        "estado_historial": estado_dashboard,
        "estado_final": estado_dashboard,
        "estado": "SIN SETUP",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# M1-SPECIFIC DETECTION WRAPPERS
# =============================================================================

def detectar_swings_m1(df_m1: pd.DataFrame) -> list:
    """
    Detecta micro swings en velas M1 con lookback reducido (2 velas).

    Reutiliza detectar_swings del engine M15 PRO con lookback=SWING_LOOKBACK_M1.

    Args:
        df_m1: DataFrame de velas M1 con columnas ['high', 'low', 'time'].

    Returns:
        Lista de swings detectados.
    """
    return detectar_swings(df_m1, lookback=SWING_LOOKBACK_M1)


def detectar_desplazamiento_impulsivo_m1(
    df_m1: pd.DataFrame,
    evento_m1: dict,
    ventana: int = DESPLAZAMIENTO_VENTANA,
    min_velas: int = DESPLAZAMIENTO_MIN_VELAS,
) -> dict:
    """
    Valida que haya un desplazamiento impulsivo fuerte después del evento M1.

    Toma las ``ventana`` velas inmediatamente después del evento estructural y
    verifica:
      - Al menos ``min_velas`` cierran en la dirección del impulso.
      - El rango total (high_max - low_min) del tramo supera MIN_ZONA_SIZE.

    Para BOS/CHOCH_ALCISTA: impulso = velas con close > open (alcistas).
    Para BOS/CHOCH_BAJISTA: impulso = velas con close < open (bajistas).

    Args:
        df_m1: DataFrame de velas M1.
        evento_m1: Evento estructural M1 con campos 'index' y 'evento'.
        ventana: Número de velas a analizar después del evento.
        min_velas: Mínimo de velas en dirección correcta para validar.

    Returns:
        dict con:
            valido (bool): True si cumple criterios de impulso.
            velas_favor (int): Velas que cierran en dirección correcta.
            rango (float): Rango total del tramo de desplazamiento.
    """
    idx = evento_m1.get("index", -1)
    direccion = "ALCISTA" if "ALCISTA" in evento_m1.get("evento", "") else "BAJISTA"

    inicio = idx + 1
    fin = min(len(df_m1), inicio + ventana)

    if inicio >= len(df_m1) or fin <= inicio:
        return {"valido": False, "velas_favor": 0, "rango": 0.0}

    tramo = df_m1.iloc[inicio:fin]

    if direccion == "ALCISTA":
        mask = tramo["close"] > tramo["open"]
    else:
        mask = tramo["close"] < tramo["open"]

    velas_favor = int(mask.sum())
    rango = float(tramo["high"].max() - tramo["low"].min()) if len(tramo) > 0 else 0.0

    valido = velas_favor >= min_velas and rango >= MIN_ZONA_SIZE

    print(f"\nDESPLAZAMIENTO_IMPULSIVO_M1:")
    print(f"  evento_index: {idx}, direccion: {direccion}")
    print(f"  velas_analizadas: {len(tramo)}, velas_favor: {velas_favor}, min_velas: {min_velas}")
    print(f"  rango: {round(rango, 4)}, MIN_ZONA_SIZE: {MIN_ZONA_SIZE}")
    print(f"  valido: {valido}")

    return {"valido": valido, "velas_favor": velas_favor, "rango": rango}


def buscar_micro_order_block(df_m1: pd.DataFrame, evento_m1: dict) -> dict:
    """
    Busca el micro Order Block asociado a un evento estructural M1.

    Alias directo de buscar_order_block del engine M15 PRO aplicado sobre
    velas M1 — la lógica es idéntica (última vela contraria antes del impulso).

    Args:
        df_m1: DataFrame de velas M1.
        evento_m1: Evento estructural M1.

    Returns:
        dict con datos del OB o None.
    """
    return buscar_order_block(df_m1, evento_m1)


# =============================================================================
# MICRO ZONE CREATION
# =============================================================================

def crear_zona_micro_impulso(
    df_m1: pd.DataFrame,
    eventos_m1: list,
    fvgs_m1: list,
    symbol: str,
    precio_actual: float,
) -> dict:
    """
    Construye la micro zona M1 combinando:
      1. Último evento estructural M1 alineado con la dirección operativa.
      2. Micro Order Block M1.
      3. Micro FVG M1.
      4. Desplazamiento impulsivo fuerte (validación adicional).
      5. Barrida local M1 (validación de manipulación/liquidez).

    Reglas de construcción de zona_desde/zona_hasta:
      - OB + FVG: unión de rangos (igual que crear_zona_m15).
      - Solo OB: rango del OB.
      - Solo FVG: rango del FVG.
      - Ninguno: rechazar zona.

    La zona también se rechaza si:
      - No hay desplazamiento impulsivo válido.
      - El tamaño de la zona es menor a MIN_ZONA_SIZE.
      - validar_zona_operativa retorna es_util=False.

    Score de confluencia:
      CHOCH +3, BOS +2, OB +2, FVG +2, barrida +3, desplazamiento +2, es_util +2.

    Args:
        df_m1: DataFrame de velas M1.
        eventos_m1: Lista de eventos estructurales M1.
        fvgs_m1: Lista de FVGs detectados en M1.
        symbol: Nombre del símbolo.
        precio_actual: Precio actual.

    Returns:
        dict con zona completa o None si ningún candidato es válido.
    """
    if not eventos_m1:
        return None

    direccion_operativa = direccion_operativa_por_indice(symbol)
    eventos_filtrados = []

    for evento in eventos_m1:
        dir_evento = "ALCISTA" if "ALCISTA" in evento["evento"] else "BAJISTA"
        if direccion_operativa and dir_evento != direccion_operativa:
            continue
        eventos_filtrados.append(evento)

    if not eventos_filtrados:
        return None

    # Verificar que el último evento no está demasiado obsoleto
    ultimo_idx = eventos_filtrados[-1]["index"]
    if (len(df_m1) - 1 - ultimo_idx) > MAX_EVENTO_STALENESS_M1:
        print(
            f"\nMICRO_IMPULSO: último evento M1 demasiado antiguo "
            f"(hace {len(df_m1) - 1 - ultimo_idx} velas > {MAX_EVENTO_STALENESS_M1}). Zona rechazada."
        )
        return None

    # Intentar crear zona desde el último evento válido hacia atrás
    for ultimo_evento in reversed(eventos_filtrados):
        direccion = "ALCISTA" if "ALCISTA" in ultimo_evento["evento"] else "BAJISTA"

        # Desplazamiento impulsivo obligatorio
        desp = detectar_desplazamiento_impulsivo_m1(df_m1, ultimo_evento)
        if not desp["valido"]:
            print(f"\nMICRO_IMPULSO: desplazamiento inválido para evento idx={ultimo_evento['index']}. Probando anterior.")
            continue

        ob = buscar_micro_order_block(df_m1, ultimo_evento)

        fvgs_validos = [
            f for f in fvgs_m1
            if f["index"] <= ultimo_evento["index"]
            and (
                (direccion == "ALCISTA" and f["tipo"] == "FVG_ALCISTA") or
                (direccion == "BAJISTA" and f["tipo"] == "FVG_BAJISTA")
            )
        ]
        fvg = fvgs_validos[-1] if fvgs_validos else None

        barrida = detectar_barrida_previa(df_m1, ultimo_evento, direccion, lookback=BARRIDA_LOOKBACK_M1)

        zona_desde = None
        zona_hasta = None

        if ob and fvg:
            zona_desde = min(ob["desde"], fvg["desde"], fvg["hasta"])
            zona_hasta = max(ob["hasta"], fvg["desde"], fvg["hasta"])
        elif ob:
            zona_desde = ob["desde"]
            zona_hasta = ob["hasta"]
        elif fvg:
            zona_desde = min(fvg["desde"], fvg["hasta"])
            zona_hasta = max(fvg["desde"], fvg["hasta"])

        if zona_desde is None:
            print(f"\nMICRO_IMPULSO: sin OB ni FVG para evento idx={ultimo_evento['index']}. Probando anterior.")
            continue

        # Rechazar zona demasiado pequeña
        if abs(zona_hasta - zona_desde) < MIN_ZONA_SIZE:
            print(
                f"\nMICRO_IMPULSO: zona demasiado pequeña "
                f"({round(abs(zona_hasta - zona_desde), 4)} < {MIN_ZONA_SIZE}). Probando anterior."
            )
            continue

        zona = {
            "direccion": direccion,
            "evento": ultimo_evento,
            "ob": ob,
            "fvg": fvg,
            "barrida": barrida,
            "desplazamiento": desp,
            "zona_desde": zona_desde,
            "zona_hasta": zona_hasta,
            "score": 0,
        }

        es_util, motivo, direccion_op = validar_zona_operativa(symbol, zona, precio_actual)

        score = 0
        if "CHOCH" in ultimo_evento["evento"]:
            score += 3
        if "BOS" in ultimo_evento["evento"]:
            score += 2
        if ob:
            score += 2
        if fvg:
            score += 2
        if barrida:
            score += 3
        if desp["valido"]:
            score += 2
        if es_util:
            score += 2

        zona["score"] = score
        zona["es_util"] = es_util
        zona["motivo"] = motivo
        zona["direccion_operativa"] = direccion_op

        print("\nEVALUATING MICRO ZONE:")
        print(f"  symbol: {symbol}")
        print(f"  zona_desde: {zona_desde}")
        print(f"  zona_hasta: {zona_hasta}")
        print(f"  precio_actual: {precio_actual}")
        print(f"  direccion: {direccion}")
        print(f"  es_util: {es_util}")
        print(f"  motivo: {motivo}")
        print(f"  score: {score}")

        if not es_util:
            print("MICRO ZONE REJECTED: es_util=False")
            continue

        print("MICRO ZONE ACCEPTED: es_util=True")
        return zona

    return None


# =============================================================================
# OPERATIONAL LEVELS — TP 1:1
# =============================================================================

def calcular_niveles_micro_impulso(zona: dict, direccion_operativa: str) -> dict:
    """
    Calcula entrada, stoploss y tp_1_1 con ratio 1:1 para SMC_MICRO_IMPULSO.

    BOOM (ALCISTA):
        entrada  = zona_hasta
        stoploss = zona_desde
        tp_1_1   = entrada + (zona_hasta - zona_desde) * 1.0

    CRASH (BAJISTA):
        entrada  = zona_desde
        stoploss = zona_hasta
        tp_1_1   = entrada - (zona_hasta - zona_desde) * 1.0

    Args:
        zona: Zona con zona_desde y zona_hasta.
        direccion_operativa: "ALCISTA" o "BAJISTA".

    Returns:
        dict con entrada, stoploss, tp_1_1.
    """
    zona_desde = zona.get("zona_desde", 0)
    zona_hasta = zona.get("zona_hasta", 0)
    zona_size = abs(zona_hasta - zona_desde)

    if direccion_operativa == "ALCISTA":
        entrada = zona_hasta
        stoploss = zona_desde
        tp_1_1 = entrada + zona_size * TP_RATIO
    else:
        entrada = zona_desde
        stoploss = zona_hasta
        tp_1_1 = entrada - zona_size * TP_RATIO

    return {
        "entrada": round(entrada, 2),
        "stoploss": round(stoploss, 2),
        "tp_1_1": round(tp_1_1, 2),
    }


# =============================================================================
# RESULT BUILDER
# =============================================================================

def _build_result(
    symbol: str,
    precio_actual: float,
    tendencia_m15: str,
    ultimo_evento_m1: str,
    zona_desde: float,
    zona_hasta: float,
    entrada: float,
    stoploss: float,
    tp_1_1: float,
    estado_dashboard: str,
    estado_historial: str,
    score: int,
    has_ob: bool,
    has_fvg: bool,
    has_barrida: bool,
    has_desplazamiento: bool,
    micro_bos_choch: str = "--",
) -> dict:
    """Construye el dict canónico de resultado para SMC_MICRO_IMPULSO."""
    return {
        "symbol": symbol,
        "price": precio_actual,
        "tendencia_m15": tendencia_m15,
        "ultimo_evento_m1": ultimo_evento_m1,
        "zona_madre_m1": {
            "desde": float(zona_desde),
            "hasta": float(zona_hasta),
        },
        "entrada": entrada,
        "stoploss": stoploss,
        "tp_1_1": tp_1_1,
        "tp_ratio": TP_RATIO,
        "score": score,
        "ob": "SI" if has_ob else "NO",
        "fvg": "SI" if has_fvg else "NO",
        "barrida": "SI" if has_barrida else "NO",
        "desplazamiento_valido": "SI" if has_desplazamiento else "NO",
        "micro_bos_choch": micro_bos_choch,
        "estado_dashboard": estado_dashboard,
        "estado_historial": estado_historial,
        "estado_final": estado_historial,
        "estado": estado_historial,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# MAIN ENGINE FUNCTION
# =============================================================================

def analyze_symbol_smc_micro_impulso_engine(
    symbol: str,
    df_m1: pd.DataFrame,
    df_m15: pd.DataFrame = None,
    **kwargs,
) -> dict:
    """
    Analiza un símbolo usando la estrategia SMC_MICRO_IMPULSO.

    M1 es el núcleo operativo completo.
    M15 es opcional (solo para campo informativo tendencia_m15).

    Flujo:
    1. Calcular swings M1, estructura M1, FVGs M1.
    2. Obtener precio actual y contexto M1.
    3. Si hay setup activo en Supabase → MODO SEGUIMIENTO.
       a. PRE-ZONA: revalidar cada ciclo (zona del lado correcto, contexto fresco).
          - Si ya no cumple: DESCARTADA / NO_CUMPLE_MICRO_IMPULSO.
          - Si hay zona fresca mejor: reemplazar zona guardada.
       b. POST-ZONA (EN_ZONA/PROFIT): bloquear zona guardada, solo actualizar estado.
          No invalidar por cambio de contexto micro.
    4. Si no hay setup activo → MODO BÚSQUEDA.
       - Crear zona micro con todos los filtros de calidad.
       - Si no hay zona válida: SIN_SETUP / NO_CUMPLE_MICRO_IMPULSO.
    5. Calcular estado dashboard y historial vía state_machine común.
    6. Retornar payload.

    Args:
        symbol: Nombre del símbolo.
        df_m1: DataFrame de velas M1 (300+ velas recomendadas).
        df_m15: DataFrame de velas M15 (opcional, informativo).
        **kwargs:
            supabase_service: Servicio Supabase.
            create_sin_setup_response: Función alternativa SIN_SETUP.
            print_result_summary: Función de resumen.

    Returns:
        dict con resultado del análisis SMC_MICRO_IMPULSO.
    """
    supabase_svc = kwargs.get("supabase_service")
    print_summary_fn = kwargs.get("print_result_summary")

    def _create_sin_setup(price=None, tendencia_m15="--", ultimo_evento_m1="--",
                          estado_db="SIN_SETUP"):
        return create_sin_setup_micro_impulso_response(
            symbol, price, tendencia_m15, ultimo_evento_m1, estado_db
        )

    def _print_summary(result):
        if callable(print_summary_fn):
            print_summary_fn(result)

    print(f"\n{'='*60}")
    print(f"SMC_MICRO_IMPULSO Analyzing {symbol}")
    print(f"{'='*60}")

    # ------------------------------------------------------------------
    # GUARD: datos mínimos
    # ------------------------------------------------------------------
    if df_m1 is None or len(df_m1) == 0:
        print(f"  ERROR: No hay datos M1 disponibles para {symbol}")
        return _create_sin_setup()

    print(f"  OK Data loaded: M1={len(df_m1)}" + (f" M15={len(df_m15)}" if df_m15 is not None else " M15=N/A"))

    try:
        # ==============================================================
        # NIVEL A: ESTRUCTURA M1 (siempre se calcula)
        # ==============================================================
        print(f"  Calculando estructura M1...")

        swings_m1 = detectar_swings_m1(df_m1)
        eventos_m1, tendencia_m1 = detectar_estructura(df_m1, swings_m1)
        fvgs_m1 = detectar_fvg(df_m1)
        precio_actual = float(df_m1["close"].iloc[-1])
        ultimo_evento_m1_str = get_last_event(eventos_m1)

        print(f"    tendencia_m1: {tendencia_m1}")
        print(f"    ultimo_evento_m1: {ultimo_evento_m1_str}")
        print(f"    precio_actual: {precio_actual}")
        print(f"    swings_m1 detectados: {len(swings_m1)}")
        print(f"    eventos_m1 detectados: {len(eventos_m1)}")
        print(f"    fvgs_m1 detectados: {len(fvgs_m1)}")

        # ==============================================================
        # NIVEL A2: CONTEXTO M15 (informativo, no bloquea)
        # ==============================================================
        tendencia_m15_str = "--"
        if df_m15 is not None and len(df_m15) > 0:
            swings_m15 = detectar_swings(df_m15, lookback=3)
            _, tendencia_m15_raw = detectar_estructura(df_m15, swings_m15)
            tendencia_m15_str = format_trend(tendencia_m15_raw)
            print(f"    tendencia_m15 (informativo): {tendencia_m15_str}")

        # Validar dirección operativa del símbolo
        direccion_operativa = direccion_operativa_por_indice(symbol)
        if not direccion_operativa:
            print(f"  SIN_SETUP: símbolo {symbol} no es Boom ni Crash")
            result = _create_sin_setup(precio_actual, tendencia_m15_str, ultimo_evento_m1_str)
            _print_summary(result)
            return result

        # ==============================================================
        # NIVEL B: MODO SEGUIMIENTO / MODO BÚSQUEDA
        # ==============================================================
        ESTADOS_SEGUIMIENTO = {"ACTIVA", "ESPERANDO_ENTRADA", "LLEGANDO_A_ZONA", "EN_ZONA", "PROFIT"}
        ESTADOS_PRE_ZONA = {"ACTIVA", "ESPERANDO_ENTRADA", "LLEGANDO_A_ZONA"}
        ESTADOS_POST_ZONA = {"EN_ZONA", "PROFIT"}

        setup_activo = None
        if supabase_svc and hasattr(supabase_svc, "get_active_setup_by_symbol"):
            setup_activo = supabase_svc.get_active_setup_by_symbol(STRATEGY_ID, symbol)

        modo_seguimiento = False
        estado_previo = None
        entrada = None
        stoploss = None
        tp_1_1 = None

        if setup_activo and setup_activo.get("estado") in ESTADOS_SEGUIMIENTO:
            estado_previo = setup_activo.get("estado")
            entrada = setup_activo.get("entrada")
            stoploss = setup_activo.get("stoploss")
            tp_1_1 = setup_activo.get("tp_1_1")

            if entrada is None or stoploss is None or tp_1_1 is None:
                print(f"  WARNING MODO SEGUIMIENTO: datos incompletos ({symbol}) — forzando MODO BUSQUEDA")
            else:
                modo_seguimiento = True

        if modo_seguimiento:
            # ----------------------------------------------------------
            # MODO SEGUIMIENTO SMC_MICRO_IMPULSO
            # ----------------------------------------------------------
            dir_op = direccion_operativa_por_indice(symbol)
            if not dir_op:
                dir_op = "ALCISTA" if entrada > stoploss else "BAJISTA"

            if dir_op == "ALCISTA":
                zona_desde = stoploss
                zona_hasta = entrada
            else:
                zona_desde = entrada
                zona_hasta = stoploss

            has_ob = bool(setup_activo.get("ob", False))
            has_fvg = bool(setup_activo.get("fvg", False))
            has_barrida = bool(setup_activo.get("barrida", False))
            has_desp = bool(setup_activo.get("desplazamiento_valido", False))
            score = int(setup_activo.get("score", 0) or 0)

            print(f"\nTRACKED_SUPABASE_ZONE (MICRO_IMPULSO):")
            print(f"  symbol: {symbol}")
            print(f"  estado_previo: {estado_previo}")
            print(f"  zona_desde: {zona_desde}")
            print(f"  zona_hasta: {zona_hasta}")
            print(f"  entrada: {entrada}")
            print(f"  stoploss: {stoploss}")
            print(f"  created_at: {setup_activo.get('created_at')}")
            print(f"  updated_at: {setup_activo.get('updated_at')}")

            print(f"\n  MODO SEGUIMIENTO MICRO_IMPULSO: usando zona guardada para {symbol}")
            print(f"    estado_previo: {estado_previo}, entrada: {entrada}, stoploss: {stoploss}, tp_1_1: {tp_1_1}")
            print(f"    zona: [{zona_desde}, {zona_hasta}], direccion: {dir_op}")

            if estado_previo in ESTADOS_PRE_ZONA:
                # ------------------------------------------------------
                # PRE-ZONA: revalidar cada ciclo
                # ------------------------------------------------------
                print(f"\n  MODO SEGUIMIENTO PRE-ZONA: comparando zonas para {symbol}...")

                en_zona_actual = (
                    (dir_op == "ALCISTA" and stoploss <= precio_actual <= entrada) or
                    (dir_op == "BAJISTA" and entrada <= precio_actual <= stoploss)
                )

                print(f"\n=== CHECK_TRACKED_ZONE_TOUCH_BEFORE_REPLACE (MICRO_IMPULSO) ===")
                print(f"  symbol: {symbol}")
                print(f"  estado_previo: {estado_previo}")
                print(f"  precio_actual: {precio_actual}")
                print(f"  entrada: {entrada}, stoploss: {stoploss}")
                print(f"  en_zona_actual: {en_zona_actual}")
                print(f"==============================================================\n")

                if en_zona_actual:
                    # Precio ya tocó la zona — bloquear como EN_ZONA
                    estado_dashboard = "EN_ZONA"
                    log_price_entered_zone_check(
                        symbol=symbol,
                        precio_actual=precio_actual,
                        entrada=entrada,
                        stoploss=stoploss,
                        zona_desde=zona_desde,
                        zona_hasta=zona_hasta,
                        direccion_operativa=dir_op,
                        en_zona_operativa=True,
                        estado_antes=estado_previo,
                        estado_despues=estado_dashboard,
                    )
                    estado_historial, _ = calcular_estado_historial(
                        symbol, estado_dashboard, precio_actual,
                        entrada, stoploss, tp_1_1, zona_desde, zona_hasta, estado_previo,
                    )
                    result = _build_result(
                        symbol, precio_actual, tendencia_m15_str, ultimo_evento_m1_str,
                        zona_desde, zona_hasta, entrada, stoploss, tp_1_1,
                        estado_dashboard, estado_historial, score,
                        has_ob, has_fvg, has_barrida, has_desp,
                        micro_bos_choch=estado_previo,
                    )
                    _print_summary(result)
                    return result

                # Validación direccional zona guardada (PRE-ZONA)
                zona_guardada_es_util, motivo_dir_val, _ = validar_zona_operativa(
                    symbol, {"zona_desde": zona_desde, "zona_hasta": zona_hasta}, precio_actual
                )

                print(f"\n=== TRACKED_ZONE_DIRECTIONAL_VALIDATION (MICRO_IMPULSO) ===")
                print(f"  symbol: {symbol}, estado_previo: {estado_previo}")
                print(f"  zona_guardada_es_util: {zona_guardada_es_util}")
                print(f"  motivo: {motivo_dir_val}")
                print(f"==========================================================\n")

                if not zona_guardada_es_util:
                    print(f"\n=== TRACKED_ZONE_INVALIDATED_PRE_TOUCH (MICRO_IMPULSO) ===")
                    print(f"  symbol: {symbol}, nuevo_estado: DESCARTADA")
                    print(f"  motivo: zona ya no está del lado correcto del precio")
                    print(f"==========================================================\n")

                    if supabase_svc and setup_activo and setup_activo.get("id"):
                        supabase_svc.update_setup(setup_activo["id"], {"estado": "DESCARTADA"})

                    result = _create_sin_setup(
                        precio_actual, tendencia_m15_str, ultimo_evento_m1_str,
                        "NO_CUMPLE_MICRO_IMPULSO",
                    )
                    _print_summary(result)
                    return result

                # Verificar staleness del contexto micro (último evento M1 reciente)
                eventos_alineados_m1 = [
                    e for e in eventos_m1
                    if (dir_op == "ALCISTA" and ("ALCISTA" in e["evento"])) or
                       (dir_op == "BAJISTA" and ("BAJISTA" in e["evento"]))
                ]
                contexto_fresco = False
                if eventos_alineados_m1:
                    ultimo_evento_alineado_idx = eventos_alineados_m1[-1]["index"]
                    velas_desde_evento = (len(df_m1) - 1) - ultimo_evento_alineado_idx
                    contexto_fresco = velas_desde_evento <= MAX_EVENTO_STALENESS_M1
                    print(f"\n=== MICRO_IMPULSO_CONTEXT_STALENESS_CHECK ===")
                    print(f"  symbol: {symbol}")
                    print(f"  ultimo_evento_alineado_idx: {ultimo_evento_alineado_idx}")
                    print(f"  velas_desde_evento: {velas_desde_evento}")
                    print(f"  MAX_EVENTO_STALENESS_M1: {MAX_EVENTO_STALENESS_M1}")
                    print(f"  contexto_fresco: {contexto_fresco}")
                    print(f"=============================================\n")

                if not contexto_fresco:
                    print(f"\n=== TRACKED_ZONE_INVALIDATED_PRE_TOUCH (MICRO_IMPULSO) ===")
                    print(f"  symbol: {symbol}, nuevo_estado: DESCARTADA")
                    print(f"  motivo: contexto micro M1 obsoleto (sin eventos alineados recientes)")
                    print(f"==========================================================\n")

                    if supabase_svc and setup_activo and setup_activo.get("id"):
                        supabase_svc.update_setup(setup_activo["id"], {"estado": "DESCARTADA"})

                    result = _create_sin_setup(
                        precio_actual, tendencia_m15_str, ultimo_evento_m1_str,
                        "NO_CUMPLE_MICRO_IMPULSO",
                    )
                    _print_summary(result)
                    return result

                # Comparar vs zona fresca — reemplazar si hay mejor candidata
                zona_fresca = crear_zona_micro_impulso(df_m1, eventos_m1, fvgs_m1, symbol, precio_actual)

                print(f"\nFRESH_MICRO_IMPULSO_ZONE:")
                print(f"  symbol: {symbol}")
                print(f"  precio_actual: {precio_actual}")
                print(f"  zona_desde: {zona_fresca['zona_desde'] if zona_fresca else None}")
                print(f"  zona_hasta: {zona_fresca['zona_hasta'] if zona_fresca else None}")
                print(f"  es_util: {zona_fresca['es_util'] if zona_fresca else None}")

                if zona_fresca and zona_fresca.get("es_util", False):
                    dir_fresca = zona_fresca.get("direccion_operativa", zona_fresca.get("direccion", dir_op))
                    niv_fresca = calcular_niveles_micro_impulso(zona_fresca, dir_fresca)
                    entrada_nueva = niv_fresca["entrada"]
                    stoploss_nueva = niv_fresca["stoploss"]
                    tp_nueva = niv_fresca["tp_1_1"]
                    z_desde_nueva = float(zona_fresca.get("zona_desde", 0))
                    z_hasta_nueva = float(zona_fresca.get("zona_hasta", 0))

                    misma_zona = (
                        round(entrada_nueva, 2) == round(entrada, 2)
                        and round(stoploss_nueva, 2) == round(stoploss, 2)
                        and round(z_desde_nueva, 2) == round(zona_desde, 2)
                        and round(z_hasta_nueva, 2) == round(zona_hasta, 2)
                    )
                    zona_cambio = not misma_zona

                    print(f"\n=== PRE_ZONE_FRESH_ZONE_COMPARISON (MICRO_IMPULSO) ===")
                    print(f"  symbol: {symbol}, estado_previo: {estado_previo}")
                    print(f"  zona_guardada: [{zona_desde}, {zona_hasta}]")
                    print(f"  zona_fresca: [{z_desde_nueva}, {z_hasta_nueva}]")
                    print(f"  misma_zona: {misma_zona}")
                    print(f"  decision: {'REPLACE_WITH_FRESH' if zona_cambio else 'KEEP_STORED'}")
                    print(f"=====================================================\n")

                    if zona_cambio:
                        entrada = entrada_nueva
                        stoploss = stoploss_nueva
                        tp_1_1 = tp_nueva
                        zona_desde = z_desde_nueva
                        zona_hasta = z_hasta_nueva
                        dir_op = dir_fresca
                        has_ob = zona_fresca.get("ob") is not None
                        has_fvg = zona_fresca.get("fvg") is not None
                        has_barrida = zona_fresca.get("barrida") is not None
                        has_desp = bool(zona_fresca.get("desplazamiento", {}).get("valido", False))
                        score = zona_fresca.get("score", 0)

                        if supabase_svc and setup_activo and setup_activo.get("id"):
                            supabase_svc.update_setup(setup_activo["id"], {
                                "entrada": entrada,
                                "stoploss": stoploss,
                                "tp_1_1": tp_1_1,
                                "score": score,
                                "ob": has_ob,
                                "fvg": has_fvg,
                                "barrida": has_barrida,
                            })
                else:
                    print(f"\n=== PRE_ZONE_FRESH_ZONE_COMPARISON (MICRO_IMPULSO) ===")
                    print(f"  symbol: {symbol}, decision: KEEP_STORED (no hay zona fresca útil)")
                    print(f"=====================================================\n")

            elif estado_previo in ESTADOS_POST_ZONA:
                # ------------------------------------------------------
                # POST-ZONA: bloquear zona guardada — trade vivo
                # NO revalidar contexto micro. Sigue hasta TP o SL.
                # ------------------------------------------------------
                print(f"\n=== ZONE_LOCKED_AFTER_EN_ZONA (MICRO_IMPULSO) ===")
                print(f"  symbol: {symbol}, estado_previo: {estado_previo}")
                print(f"  entrada: {entrada}, stoploss: {stoploss}")
                print(f"  Trade vivo — no se invalida por cambio de contexto micro.")
                print(f"=================================================\n")

            # EN_ZONA prioridad absoluta en MODO SEGUIMIENTO
            en_zona_seg = (
                (dir_op == "ALCISTA" and stoploss <= precio_actual <= entrada) or
                (dir_op == "BAJISTA" and entrada <= precio_actual <= stoploss)
            )

            if en_zona_seg:
                estado_dashboard = "EN_ZONA"
                log_price_entered_zone_check(
                    symbol=symbol,
                    precio_actual=precio_actual,
                    entrada=entrada,
                    stoploss=stoploss,
                    zona_desde=zona_desde,
                    zona_hasta=zona_hasta,
                    direccion_operativa=dir_op,
                    en_zona_operativa=True,
                    estado_antes=estado_previo,
                    estado_despues=estado_dashboard,
                )
            else:
                estado_dashboard = calcular_estado_dashboard(
                    precio_actual, entrada, zona_desde, zona_hasta,
                    dir_op, df_m1=df_m1, symbol=symbol,
                )

            print(f"  Estado Dashboard (MODO SEGUIMIENTO): {estado_dashboard}")

            estado_historial, motivo_transicion = calcular_estado_historial(
                symbol, estado_dashboard, precio_actual,
                entrada, stoploss, tp_1_1, zona_desde, zona_hasta, estado_previo,
            )
            print(f"  Estado Historial (validado): {estado_historial}, motivo: {motivo_transicion}")

            result = _build_result(
                symbol, precio_actual, tendencia_m15_str, ultimo_evento_m1_str,
                zona_desde, zona_hasta, entrada, stoploss, tp_1_1,
                estado_dashboard, estado_historial, score,
                has_ob, has_fvg, has_barrida, has_desp,
                micro_bos_choch=estado_previo,
            )
            _print_summary(result)
            return result

        # ==============================================================
        # MODO BÚSQUEDA — no hay setup activo SMC_MICRO_IMPULSO
        # ==============================================================
        print(f"  MODO BUSQUEDA MICRO_IMPULSO: buscando zona nueva para {symbol}...")

        print(f"\nTRACKED_SUPABASE_ZONE (MICRO_IMPULSO):")
        print(f"  symbol: {symbol}")
        print(f"  estado_previo: NINGUNO")
        print(f"  zona_desde: None")
        print(f"  zona_hasta: None")
        print(f"  entrada: None")
        print(f"  stoploss: None")

        zona = crear_zona_micro_impulso(df_m1, eventos_m1, fvgs_m1, symbol, precio_actual)

        if not zona:
            print(f"  NO_CUMPLE_MICRO_IMPULSO: sin zona micro válida para {symbol}")
            result = _create_sin_setup(
                precio_actual, tendencia_m15_str, ultimo_evento_m1_str,
                "NO_CUMPLE_MICRO_IMPULSO",
            )
            _print_summary(result)
            return result

        print(f"  MICRO ZONE created: [{zona['zona_desde']}, {zona['zona_hasta']}] dir={zona['direccion']}")

        has_ob = zona.get("ob") is not None
        has_fvg = zona.get("fvg") is not None
        has_barrida = zona.get("barrida") is not None
        has_desp = bool(zona.get("desplazamiento", {}).get("valido", False))
        score = zona.get("score", 0)
        dir_op = zona.get("direccion_operativa", zona.get("direccion", "ALCISTA"))

        niveles = calcular_niveles_micro_impulso(zona, dir_op)
        entrada = niveles["entrada"]
        stoploss = niveles["stoploss"]
        tp_1_1 = niveles["tp_1_1"]
        zona_desde = float(zona.get("zona_desde", 0))
        zona_hasta = float(zona.get("zona_hasta", 0))
        micro_bos_choch = zona.get("evento", {}).get("evento", "--")

        print(f"    entrada: {entrada}, stoploss: {stoploss}, tp_1_1: {tp_1_1}")

        estado_dashboard = calcular_estado_dashboard(
            precio_actual, entrada, zona_desde, zona_hasta,
            dir_op, df_m1=df_m1, symbol=symbol,
        )
        print(f"  Estado Dashboard (calculado): {estado_dashboard}")

        # Obtener estado previo (MODO BÚSQUEDA — misma zona exacta)
        estado_previo_busqueda = None
        if supabase_svc and hasattr(supabase_svc, "get_active_setup"):
            existing = supabase_svc.get_active_setup(STRATEGY_ID, symbol, entrada, stoploss)
            if existing:
                estado_previo_busqueda = existing.get("estado")
                print(f"  Estado Previo (guardado): {estado_previo_busqueda}")
            else:
                print(f"  Estado Previo: NINGUNO (nueva zona)")

        estado_historial, motivo_transicion = calcular_estado_historial(
            symbol, estado_dashboard, precio_actual,
            entrada, stoploss, tp_1_1, zona_desde, zona_hasta, estado_previo_busqueda,
        )
        print(f"  Estado Historial (validado): {estado_historial}, motivo: {motivo_transicion}")

        if estado_historial == "SIN_SETUP":
            print(f"  Zona inválida para dashboard — retornando SIN SETUP")
            result = _create_sin_setup(
                precio_actual, tendencia_m15_str, ultimo_evento_m1_str,
            )
            _print_summary(result)
            return result

        print(f"\n=== LOG TRANSICION ESTADO {symbol} (MICRO_IMPULSO) ===")
        print(f"  estado_previo: {estado_previo_busqueda if estado_previo_busqueda else 'NINGUNO'}")
        print(f"  estado_calculado: {estado_dashboard}")
        print(f"  estado_validado: {estado_historial}")
        print(f"  entrada: {entrada}, stoploss: {stoploss}, tp_1_1: {tp_1_1}")
        print(f"  motivo_transicion: {motivo_transicion}")
        print(f"========================================================\n")

        result = _build_result(
            symbol, precio_actual, tendencia_m15_str, ultimo_evento_m1_str,
            zona_desde, zona_hasta, entrada, stoploss, tp_1_1,
            estado_dashboard, estado_historial, score,
            has_ob, has_fvg, has_barrida, has_desp,
            micro_bos_choch=micro_bos_choch,
        )
        _print_summary(result)
        return result

    except Exception as e:
        print(f"  ERROR analyzing {symbol} (MICRO_IMPULSO): {e}")
        traceback.print_exc()
        return _create_sin_setup(precio_actual if 'precio_actual' in dir() else None)


# =============================================================================
# ENGINE CLASS
# =============================================================================

class SMCMicroImpulsoEngine(BaseStrategy):
    """SMC MICRO IMPULSO strategy engine."""

    strategy_id = STRATEGY_ID
    strategy_name = STRATEGY_NAME

    def analyze(self, symbol, df_h1, df_m15, df_m1=None, **kwargs):
        """
        Analiza símbolo.

        Args:
            symbol: Nombre del símbolo.
            df_h1: H1 DataFrame — no se usa por esta estrategia (aceptado por interfaz).
            df_m15: M15 DataFrame — solo informativo.
            df_m1: M1 DataFrame — núcleo operativo.
            **kwargs: Contexto adicional (supabase_service, etc.).

        Returns:
            dict con resultado SMC_MICRO_IMPULSO.
        """
        return analyze_symbol_smc_micro_impulso_engine(
            symbol, df_m1=df_m1, df_m15=df_m15, **kwargs
        )
