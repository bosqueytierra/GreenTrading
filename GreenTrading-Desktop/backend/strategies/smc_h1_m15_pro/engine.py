#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SMC H1 + M15 PRO strategy engine (FASE 3A).

Estrategia dual-temporalidad:
  - H1: filtro direccional obligatorio (ALCISTA/BAJISTA)
  - M15: núcleo operativo completo (BOS/CHOCH/OB/FVG/Barrida)

Diferencias clave vs SMC_M15_PRO:
  - Requiere alineación H1 + último evento M15 antes de crear zona
  - TP ratio 1:2 (guardado en campo tp_1_1 por compatibilidad)
  - strategy_id = "SMC_H1_M15_PRO" — completamente aislado en Supabase
  - Sin uso de M1
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
    crear_zona_m15,
    calcular_niveles_operativos,
    format_trend,
    get_last_event,
    log_fresh_master_style_zone,
    log_tracked_supabase_zone,
)

STRATEGY_ID = "SMC_H1_M15_PRO"
STRATEGY_NAME = "SMC H1 + M15 PRO"
TP_RATIO = 2.0

SWING_LOOKBACK = 3

# Eventos M15 alineados por dirección operativa
EVENTOS_ALINEADOS_ALCISTA = {"BOS_ALCISTA", "CHOCH_ALCISTA"}
EVENTOS_ALINEADOS_BAJISTA = {"BOS_BAJISTA", "CHOCH_BAJISTA"}


# =========================
# TP 1:2 CALCULATOR
# =========================

def calcular_niveles_operativos_1_2(zona: dict, direccion_operativa: str) -> dict:
    """
    Calcula entrada, stoploss y tp_1_1 con ratio 1:2 según la zona y dirección.

    BOOM (ALCISTA):
        entrada = zona_hasta
        stoploss = zona_desde
        tp = entrada + ((entrada - stoploss) * 2)

    CRASH (BAJISTA):
        entrada = zona_desde
        stoploss = zona_hasta
        tp = entrada - ((stoploss - entrada) * 2)

    Nota: el campo tp_1_1 alberga el TP operativo (1:2 para esta estrategia)
    por compatibilidad con el schema de Supabase.

    Args:
        zona: Zona con zona_desde y zona_hasta
        direccion_operativa: "ALCISTA" o "BAJISTA"

    Returns:
        dict con entrada, stoploss, tp_1_1 (valor 1:2)
    """
    zona_desde = zona.get("zona_desde", 0)
    zona_hasta = zona.get("zona_hasta", 0)
    zona_size = abs(zona_hasta - zona_desde)

    if direccion_operativa == "ALCISTA":
        entrada = zona_hasta
        stoploss = zona_desde
        tp_1_1 = entrada + (zona_size * TP_RATIO)
    else:
        entrada = zona_desde
        stoploss = zona_hasta
        tp_1_1 = entrada - (zona_size * TP_RATIO)

    return {
        "entrada": round(entrada, 2),
        "stoploss": round(stoploss, 2),
        "tp_1_1": round(tp_1_1, 2),
    }


# =========================
# SIN SETUP RESPONSE
# =========================

def create_sin_setup_h1m15_response(
    symbol: str,
    price: float = None,
    tendencia_h1: str = "--",
    tendencia_m15: str = "--",
    ultimo_evento_m15: str = "--",
    estado_dashboard: str = "SIN_SETUP",
) -> dict:
    """
    Crea respuesta mínima SIN SETUP para SMC_H1_M15_PRO.

    Args:
        symbol: Symbol name
        price: Current price (optional)
        tendencia_h1: H1 trend (optional, for informational display)
        tendencia_m15: M15 trend (optional)
        ultimo_evento_m15: Last M15 event (optional)
        estado_dashboard: Dashboard state (default SIN_SETUP,
            use NO_CUMPLE_CONDICIONES_H1_M15 when H1/M15 not aligned)

    Returns:
        dict with minimal response structure compatible with snapshot shape
    """
    return {
        "symbol": symbol,
        "price": price,
        "tendencia_h1": tendencia_h1,
        "tendencia_m15": tendencia_m15,
        "ultimo_evento_m15": ultimo_evento_m15,
        "zona_madre_m15": {"desde": 0, "hasta": 0},
        "entrada": None,
        "stoploss": None,
        "tp_1_1": None,
        "tp_ratio": TP_RATIO,
        "score": 0,
        "ob": "NO",
        "fvg": "NO",
        "barrida": "NO",
        "estado_dashboard": estado_dashboard,
        "estado_historial": estado_dashboard,
        "estado_final": estado_dashboard,
        "estado": "SIN SETUP",
        "alineacion_h1": tendencia_h1,
        "estado_h1_m15": "NO_CUMPLE" if estado_dashboard == "NO_CUMPLE_CONDICIONES_H1_M15" else "SIN_SETUP",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


# =========================
# H1 ALIGNMENT CHECK
# =========================

def verificar_alineacion_h1_m15(
    symbol: str,
    tendencia_h1: str,
    ultimo_evento_m15: str,
    precio_actual: float,
) -> tuple:
    """
    Verifica la alineación obligatoria entre H1 y M15.

    BOOM (ALCISTA):
        H1 debe ser ALCISTA
        último evento M15 debe ser BOS_ALCISTA o CHOCH_ALCISTA

    CRASH (BAJISTA):
        H1 debe ser BAJISTA
        último evento M15 debe ser BOS_BAJISTA o CHOCH_BAJISTA

    Para símbolos no clasificados como Boom/Crash: siempre OK.

    Args:
        symbol: Symbol name
        tendencia_h1: H1 trend detected ("ALCISTA"/"BAJISTA"/None)
        ultimo_evento_m15: Last M15 structural event string
        precio_actual: Current price (for logging)

    Returns:
        Tuple (alineado: bool, motivo: str)
    """
    direccion_operativa = direccion_operativa_por_indice(symbol)

    print(f"\n=== H1_M15_ALIGNMENT_CHECK [{symbol}] ===")
    print(f"  precio_actual: {precio_actual}")
    print(f"  direccion_operativa: {direccion_operativa}")
    print(f"  tendencia_h1: {tendencia_h1}")
    print(f"  ultimo_evento_m15: {ultimo_evento_m15}")

    if direccion_operativa is None:
        print(f"  resultado: ALINEADO (simbolo no clasificado Boom/Crash)")
        print(f"==========================================\n")
        return True, "Símbolo no clasificado como Boom/Crash — filtro H1 no aplica"

    if direccion_operativa == "ALCISTA":
        h1_ok = tendencia_h1 == "ALCISTA"
        evento_ok = ultimo_evento_m15 in EVENTOS_ALINEADOS_ALCISTA
        motivo_base = "BOOM"
    else:
        h1_ok = tendencia_h1 == "BAJISTA"
        evento_ok = ultimo_evento_m15 in EVENTOS_ALINEADOS_BAJISTA
        motivo_base = "CRASH"

    alineado = h1_ok and evento_ok

    if not alineado:
        razones = []
        if not h1_ok:
            razones.append(f"H1={tendencia_h1} (requiere {direccion_operativa})")
        if not evento_ok:
            razones.append(f"evento_m15={ultimo_evento_m15} (requiere BOS/CHOCH_{direccion_operativa})")
        motivo = f"{motivo_base}: NO cumple — {', '.join(razones)}"
    else:
        motivo = f"{motivo_base}: alineación H1+M15 confirmada"

    print(f"  h1_ok: {h1_ok}")
    print(f"  evento_ok: {evento_ok}")
    print(f"  alineado: {alineado}")
    print(f"  motivo: {motivo}")
    print(f"==========================================\n")

    return alineado, motivo


# =========================
# MAIN ANALYSIS FUNCTION
# =========================

def analyze_symbol_smc_h1m15_engine(
    symbol: str,
    df_h1: pd.DataFrame,
    df_m15: pd.DataFrame,
    df_m1: pd.DataFrame = None,
    **kwargs,
) -> dict:
    """
    Analyze a symbol using SMC_H1_M15_PRO strategic orchestration.

    FASE 3A: estrategia dual-temporalidad completamente separada de SMC_M15_PRO.

    Flujo:
    1. Calcular SIEMPRE swings y estructura para H1 y M15
    2. Obtener tendencia_h1, tendencia_m15, ultimo_evento_m15
    3. MODO SEGUIMIENTO si hay setup activo SMC_H1_M15_PRO (aislado de SMC_M15_PRO)
    4. MODO BÚSQUEDA: verificar alineación H1+M15 ANTES de crear zona
       - Si NO alineado: retornar NO_CUMPLE_CONDICIONES_H1_M15
       - Si alineado: crear zona M15 y calcular niveles con TP 1:2
    5. Calcular estado dashboard / historial via state_machine.py (sin cambios)
    6. Retornar payload con campos extra: tp_ratio, alineacion_h1, estado_h1_m15

    Args:
        symbol: Symbol name
        df_h1: H1 candles DataFrame (filtro direccional)
        df_m15: M15 candles DataFrame (núcleo operativo)
        df_m1: M1 candles DataFrame (NO se usa, aceptado por compatibilidad de interfaz)
        **kwargs:
            supabase_service: Supabase service instance
            create_sin_setup_response: fallback response creator
            print_result_summary: result summary printer

    Returns:
        dict with SMC H1+M15 PRO analysis results
    """
    supabase_service = kwargs.get("supabase_service")
    create_sin_setup_response_fn = kwargs.get("create_sin_setup_response")
    print_result_summary_fn = kwargs.get("print_result_summary")

    def _create_sin_setup(price=None, tendencia_h1="--", tendencia_m15="--",
                          ultimo_evento="--", estado_db="SIN_SETUP"):
        if callable(create_sin_setup_response_fn):
            base = create_sin_setup_response_fn(symbol, price)
            base.update({
                "tp_ratio": TP_RATIO,
                "alineacion_h1": tendencia_h1,
                "estado_h1_m15": (
                    "NO_CUMPLE" if estado_db == "NO_CUMPLE_CONDICIONES_H1_M15"
                    else "SIN_SETUP"
                ),
                "estado_dashboard": estado_db,
                "estado_historial": estado_db,
                "estado_final": estado_db,
            })
            return base
        return create_sin_setup_h1m15_response(
            symbol, price, tendencia_h1, tendencia_m15, ultimo_evento, estado_db
        )

    def _print_summary(result):
        if callable(print_result_summary_fn):
            print_result_summary_fn(result)

    print(f"\n{'='*60}")
    print(f"SMC_H1_M15_PRO Analyzing {symbol}")
    print(f"{'='*60}")

    # ------------------------------------------------------------------
    # GUARD: datos mínimos
    # ------------------------------------------------------------------
    if df_h1 is None or df_m15 is None or len(df_h1) == 0 or len(df_m15) == 0:
        print(f"  ERROR No data available for {symbol}")
        return _create_sin_setup()

    print(f"  OK Data loaded: H1={len(df_h1)} M15={len(df_m15)}")

    try:
        # ==============================================================
        # NIVEL A: ESTRUCTURA BASE (siempre se calcula)
        # ==============================================================
        print(f"  Calculating base structure...")

        swings_h1 = detectar_swings(df_h1, SWING_LOOKBACK)
        swings_m15 = detectar_swings(df_m15, SWING_LOOKBACK)

        eventos_h1, tendencia_h1 = detectar_estructura(df_h1, swings_h1)
        eventos_m15, tendencia_m15 = detectar_estructura(df_m15, swings_m15)

        ultimo_evento_m15 = get_last_event(eventos_m15)
        precio_actual = float(df_m15["close"].iloc[-1])

        print(f"    tendencia_h1: {tendencia_h1}, tendencia_m15: {tendencia_m15}")
        print(f"    ultimo_evento_m15: {ultimo_evento_m15}")
        print(f"    precio_actual: {precio_actual}")

        # ==============================================================
        # NIVEL B: SETUP / ZONA — con MODO SEGUIMIENTO / MODO BÚSQUEDA
        # El MODO SEGUIMIENTO es EXCLUSIVO de SMC_H1_M15_PRO (aislado por strategy_id)
        # ==============================================================

        ESTADOS_SEGUIMIENTO = {"ACTIVA", "ESPERANDO_ENTRADA", "LLEGANDO_A_ZONA", "EN_ZONA", "PROFIT"}
        ESTADOS_PRE_ZONA = {"ACTIVA", "ESPERANDO_ENTRADA", "LLEGANDO_A_ZONA"}
        ESTADOS_POST_ZONA = {"EN_ZONA", "PROFIT"}

        setup_activo = None
        if supabase_service:
            setup_activo = supabase_service.get_active_setup_by_symbol(STRATEGY_ID, symbol)

        modo_seguimiento = False
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
            # MODO SEGUIMIENTO SMC_H1_M15_PRO
            # Igual lógica que SMC_M15_PRO pero con strategy_id aislado
            # y tp_1_1 guardado como 1:2 ratio
            # ----------------------------------------------------------
            direccion_operativa = direccion_operativa_por_indice(symbol)
            if not direccion_operativa:
                direccion_operativa = "ALCISTA" if entrada > stoploss else "BAJISTA"

            if direccion_operativa == "ALCISTA":
                zona_desde = stoploss
                zona_hasta = entrada
            else:
                zona_desde = entrada
                zona_hasta = stoploss

            has_ob = bool(setup_activo.get("ob", False))
            has_fvg = bool(setup_activo.get("fvg", False))
            has_barrida = bool(setup_activo.get("barrida", False))
            score = setup_activo.get("score", 0) or 0

            log_tracked_supabase_zone(
                symbol=symbol,
                estado_previo=estado_previo,
                zona_desde=zona_desde,
                zona_hasta=zona_hasta,
                entrada=entrada,
                stoploss=stoploss,
                created_at=setup_activo.get("created_at"),
                updated_at=setup_activo.get("updated_at"),
            )

            # Zona fresca para comparación PRE-ZONA
            fvgs_m15_seg = detectar_fvg(df_m15)
            zona_fresca_master = crear_zona_m15(df_m15, eventos_m15, fvgs_m15_seg, symbol, precio_actual)
            log_fresh_master_style_zone(symbol, precio_actual, zona_fresca_master)

            print(f"  MODO SEGUIMIENTO SMC_H1_M15_PRO: usando zona guardada para {symbol}")
            print(f"    estado_previo: {estado_previo}, entrada: {entrada}, stoploss: {stoploss}, tp_1_1: {tp_1_1}")
            print(f"    zona: [{zona_desde}, {zona_hasta}], direccion: {direccion_operativa}")

            # ----------------------------------------------------------
            # PRE-ZONA: comparar zona guardada vs zona fresca
            # ----------------------------------------------------------
            # _estado_h1m15_seg drives the estado_h1_m15 field in the
            # payload built at the common MODO SEGUIMIENTO exit below.
            # It must be initialized here (before the if/elif branches)
            # because the common exit is also reached from POST-ZONA,
            # where no re-validation happens and "SEGUIMIENTO" is correct.
            #   "ALINEADO"    — PRE-ZONA, context confirmed this cycle
            #   "SEGUIMIENTO" — POST-ZONA (not re-validated by design)
            _estado_h1m15_seg = "SEGUIMIENTO"

            if estado_previo in ESTADOS_PRE_ZONA:
                print(f"  MODO SEGUIMIENTO PRE-ZONA: comparando zonas para {symbol}...")

                en_zona_actual = (
                    (direccion_operativa == "ALCISTA" and stoploss <= precio_actual <= entrada) or
                    (direccion_operativa == "BAJISTA" and entrada <= precio_actual <= stoploss)
                )

                print(f"\n=== CHECK_TRACKED_ZONE_TOUCH_BEFORE_REPLACE (H1M15) ===")
                print(f"  symbol: {symbol}")
                print(f"  estado_previo: {estado_previo}")
                print(f"  precio_actual: {precio_actual}")
                print(f"  entrada: {entrada}, stoploss: {stoploss}")
                print(f"  en_zona_actual: {en_zona_actual}")
                print(f"=======================================================\n")

                if en_zona_actual:
                    # Precio ya tocó la zona guardada: bloquear como EN_ZONA
                    estado_dashboard = "EN_ZONA"
                    log_price_entered_zone_check(
                        symbol=symbol,
                        precio_actual=precio_actual,
                        entrada=entrada,
                        stoploss=stoploss,
                        zona_desde=zona_desde,
                        zona_hasta=zona_hasta,
                        direccion_operativa=direccion_operativa,
                        en_zona_operativa=True,
                        estado_antes=estado_previo,
                        estado_despues=estado_dashboard,
                    )

                    estado_historial, motivo_transicion = calcular_estado_historial(
                        symbol, estado_dashboard, precio_actual,
                        entrada, stoploss, tp_1_1, zona_desde, zona_hasta, estado_previo
                    )

                    result = _build_result(
                        symbol, precio_actual, tendencia_h1, tendencia_m15, ultimo_evento_m15,
                        zona_desde, zona_hasta, entrada, stoploss, tp_1_1,
                        estado_dashboard, estado_historial, score, has_ob, has_fvg, has_barrida,
                    )
                    _print_summary(result)
                    return result

                # ----------------------------------------------------------
                # H1+M15 context re-validation — every PRE-ZONA cycle
                # Boom: H1 ALCISTA + ultimo_evento_m15 BOS/CHOCH_ALCISTA
                # Crash: H1 BAJISTA + ultimo_evento_m15 BOS/CHOCH_BAJISTA
                # If the context no longer holds, mark DESCARTADA and return
                # NO_CUMPLE_CONDICIONES_H1_M15. EN_ZONA/PROFIT are never
                # invalidated — the operation is already live.
                # ----------------------------------------------------------
                alineado_seg, motivo_alineacion_seg = verificar_alineacion_h1_m15(
                    symbol, tendencia_h1, ultimo_evento_m15, precio_actual
                )

                print(f"\n=== H1M15_TRACKED_CONTEXT_VALIDATION ===")
                print(f"  symbol: {symbol}")
                print(f"  estado_previo: {estado_previo}")
                print(f"  tendencia_h1: {tendencia_h1}")
                print(f"  ultimo_evento_m15: {ultimo_evento_m15}")
                print(f"  direccion_operativa: {direccion_operativa}")
                print(f"  alineado: {alineado_seg}")
                print(f"  motivo: {motivo_alineacion_seg}")
                print(f"=========================================\n")

                if not alineado_seg:
                    print(f"\n=== H1M15_TRACKED_CONTEXT_INVALIDATED_PRE_TOUCH ===")
                    print(f"  symbol: {symbol}")
                    print(f"  estado_previo: {estado_previo}")
                    print(f"  nuevo_estado: DESCARTADA")
                    print(f"  motivo: contexto H1+M15 ya no cumple antes de tocar zona")
                    print(f"====================================================\n")

                    if supabase_service and setup_activo and setup_activo.get("id"):
                        supabase_service.update_setup(setup_activo["id"], {"estado": "DESCARTADA"})

                    result = _create_sin_setup(
                        precio_actual, format_trend(tendencia_h1),
                        format_trend(tendencia_m15), ultimo_evento_m15,
                        "NO_CUMPLE_CONDICIONES_H1_M15",
                    )
                    _print_summary(result)
                    return result

                # Context confirmed — mark for payload
                _estado_h1m15_seg = "ALINEADO"

                # Validación direccional zona guardada (PRE-ZONA)
                zona_guardada_es_util, motivo_dir_val, _ = validar_zona_operativa(
                    symbol, {"zona_desde": zona_desde, "zona_hasta": zona_hasta}, precio_actual
                )

                print(f"\n=== TRACKED_ZONE_DIRECTIONAL_VALIDATION (H1M15) ===")
                print(f"  symbol: {symbol}, estado_previo: {estado_previo}")
                print(f"  zona_guardada_es_util: {zona_guardada_es_util}")
                print(f"  motivo: {motivo_dir_val}")
                print(f"===================================================\n")

                if not zona_guardada_es_util:
                    print(f"\n=== TRACKED_ZONE_INVALIDATED_PRE_TOUCH (H1M15) ===")
                    print(f"  symbol: {symbol}, nuevo_estado: DESCARTADA")
                    print(f"====================================================\n")

                    if supabase_service and setup_activo and setup_activo.get("id"):
                        supabase_service.update_setup(setup_activo["id"], {"estado": "DESCARTADA"})

                    result = _create_sin_setup(precio_actual, format_trend(tendencia_h1),
                                               format_trend(tendencia_m15), ultimo_evento_m15)
                    _print_summary(result)
                    return result

                # Comparar vs zona fresca
                decision_pre_zone = "NO_FRESH_ZONE"
                if zona_fresca_master:
                    dir_cand = zona_fresca_master.get(
                        "direccion_operativa", zona_fresca_master.get("direccion", direccion_operativa)
                    )
                    # Para TP 1:2 usamos calcular_niveles_operativos_1_2
                    niv_cand = calcular_niveles_operativos_1_2(zona_fresca_master, dir_cand)
                    entrada_nueva = niv_cand["entrada"]
                    stoploss_nueva = niv_cand["stoploss"]
                    tp_nueva = niv_cand["tp_1_1"]
                    z_desde_nueva = float(zona_fresca_master.get("zona_desde", 0))
                    z_hasta_nueva = float(zona_fresca_master.get("zona_hasta", 0))
                    score_nueva = zona_fresca_master.get("score", 0)

                    es_util_dir_fresca, _, _ = validar_zona_operativa(
                        symbol, {"zona_desde": z_desde_nueva, "zona_hasta": z_hasta_nueva}, precio_actual
                    )
                    zona_fresca_es_util = bool(zona_fresca_master.get("es_util", False)) and es_util_dir_fresca

                    misma_zona = (
                        round(entrada_nueva, 2) == round(entrada, 2)
                        and round(stoploss_nueva, 2) == round(stoploss, 2)
                        and round(z_desde_nueva, 2) == round(zona_desde, 2)
                        and round(z_hasta_nueva, 2) == round(zona_hasta, 2)
                    )

                    zona_cambio = zona_fresca_es_util and not misma_zona
                    decision_pre_zone = "REPLACE_WITH_FRESH" if zona_cambio else "KEEP_STORED"

                    print(f"\n=== PRE_ZONE_FRESH_ZONE_COMPARISON (H1M15) ===")
                    print(f"  symbol: {symbol}, estado_previo: {estado_previo}")
                    print(f"  zona_guardada: [{zona_desde}, {zona_hasta}]")
                    print(f"  zona_fresca: [{z_desde_nueva}, {z_hasta_nueva}]")
                    print(f"  zona_fresca_es_util: {zona_fresca_es_util}")
                    print(f"  misma_zona: {misma_zona}, decision: {decision_pre_zone}")
                    print(f"=============================================\n")

                    if zona_cambio:
                        entrada = entrada_nueva
                        stoploss = stoploss_nueva
                        tp_1_1 = tp_nueva
                        zona_desde = z_desde_nueva
                        zona_hasta = z_hasta_nueva
                        direccion_operativa = dir_cand
                        has_ob = zona_fresca_master.get("ob") is not None
                        has_fvg = zona_fresca_master.get("fvg") is not None
                        has_barrida = zona_fresca_master.get("barrida") is not None
                        score = score_nueva

                        if supabase_service and setup_activo and setup_activo.get("id"):
                            supabase_service.update_setup(setup_activo["id"], {
                                "entrada": entrada, "stoploss": stoploss, "tp_1_1": tp_1_1,
                                "score": score, "ob": has_ob, "fvg": has_fvg, "barrida": has_barrida,
                            })

            # ----------------------------------------------------------
            # POST-ZONA: bloquear zona guardada (EN_ZONA / PROFIT)
            # ----------------------------------------------------------
            elif estado_previo in ESTADOS_POST_ZONA:
                print(f"\n=== ZONE_LOCKED_AFTER_EN_ZONA (H1M15) ===")
                print(f"  symbol: {symbol}, estado_previo: {estado_previo}")
                print(f"  entrada: {entrada}, stoploss: {stoploss}")
                print(f"==========================================\n")

            # EN_ZONA prioridad absoluta en MODO SEGUIMIENTO
            en_zona_seguimiento = (
                (direccion_operativa == "ALCISTA" and stoploss <= precio_actual <= entrada) or
                (direccion_operativa == "BAJISTA" and entrada <= precio_actual <= stoploss)
            )

            if en_zona_seguimiento:
                estado_dashboard = "EN_ZONA"
                log_price_entered_zone_check(
                    symbol=symbol, precio_actual=precio_actual,
                    entrada=entrada, stoploss=stoploss,
                    zona_desde=zona_desde, zona_hasta=zona_hasta,
                    direccion_operativa=direccion_operativa, en_zona_operativa=True,
                    estado_antes=estado_previo, estado_despues=estado_dashboard,
                )
            else:
                estado_dashboard = calcular_estado_dashboard(
                    precio_actual, entrada, zona_desde, zona_hasta,
                    direccion_operativa, df_m1=None, symbol=symbol,
                )

            print(f"  Estado Dashboard (MODO SEGUIMIENTO): {estado_dashboard}")

            estado_historial, motivo_transicion = calcular_estado_historial(
                symbol, estado_dashboard, precio_actual,
                entrada, stoploss, tp_1_1, zona_desde, zona_hasta, estado_previo,
            )
            print(f"  Estado Historial (validado): {estado_historial}, motivo: {motivo_transicion}")

            result = _build_result(
                symbol, precio_actual, tendencia_h1, tendencia_m15, ultimo_evento_m15,
                zona_desde, zona_hasta, entrada, stoploss, tp_1_1,
                estado_dashboard, estado_historial, score, has_ob, has_fvg, has_barrida,
                estado_h1_m15_override=_estado_h1m15_seg,
            )
            _print_summary(result)
            return result

        # ==============================================================
        # MODO BÚSQUEDA: no hay setup activo SMC_H1_M15_PRO
        # ==============================================================
        print(f"  MODO BUSQUEDA SMC_H1_M15_PRO: buscando zona nueva para {symbol}...")

        log_tracked_supabase_zone(
            symbol=symbol, estado_previo="NINGUNO",
            zona_desde=None, zona_hasta=None,
            entrada=None, stoploss=None, created_at=None, updated_at=None,
        )

        # ----------------------------------------------------------
        # NIVEL C: FILTRO H1 OBLIGATORIO
        # Solo se crea zona si H1 + ultimo evento M15 están alineados
        # ----------------------------------------------------------
        alineado, motivo_alineacion = verificar_alineacion_h1_m15(
            symbol, tendencia_h1, ultimo_evento_m15, precio_actual
        )

        if not alineado:
            print(f"  NO_CUMPLE_CONDICIONES_H1_M15: {motivo_alineacion}")
            result = _create_sin_setup(
                precio_actual,
                format_trend(tendencia_h1),
                format_trend(tendencia_m15),
                ultimo_evento_m15,
                "NO_CUMPLE_CONDICIONES_H1_M15",
            )
            _print_summary(result)
            return result

        print(f"  H1+M15 ALINEADOS: {motivo_alineacion}")
        print(f"  Procediendo a construcción de zona M15...")

        # ----------------------------------------------------------
        # NIVEL D: ZONA M15 (misma lógica que SMC_M15_PRO)
        # ----------------------------------------------------------
        fvgs_m15 = detectar_fvg(df_m15)
        zona = crear_zona_m15(df_m15, eventos_m15, fvgs_m15, symbol, precio_actual)
        log_fresh_master_style_zone(symbol, precio_actual, zona)

        if not zona:
            print(f"  NO ZONE created (no OB/FVG or not operative)")
            result = _create_sin_setup(
                precio_actual, format_trend(tendencia_h1),
                format_trend(tendencia_m15), ultimo_evento_m15,
            )
            _print_summary(result)
            return result

        print(f"  ZONE created: [{zona['zona_desde']}, {zona['zona_hasta']}] dir={zona['direccion']}")

        has_ob = zona.get("ob") is not None
        has_fvg = zona.get("fvg") is not None
        has_barrida = zona.get("barrida") is not None
        es_util = zona.get("es_util", False)
        score = zona.get("score", 0)
        direccion_operativa = zona.get("direccion_operativa", zona.get("direccion", "ALCISTA"))

        # Niveles operativos con TP 1:2
        niveles = calcular_niveles_operativos_1_2(zona, direccion_operativa)
        entrada = niveles["entrada"]
        stoploss = niveles["stoploss"]
        tp_1_1 = niveles["tp_1_1"]
        zona_desde = float(zona.get("zona_desde", 0))
        zona_hasta = float(zona.get("zona_hasta", 0))

        print(f"    entrada: {entrada}, stoploss: {stoploss}, tp_1_1 (1:2): {tp_1_1}")

        # M1 NO se usa en esta estrategia
        estado_dashboard = calcular_estado_dashboard(
            precio_actual, entrada, zona_desde, zona_hasta,
            direccion_operativa, df_m1=None, symbol=symbol,
        )
        print(f"  Estado Dashboard (calculado): {estado_dashboard}")

        # Estado previo (MODO BÚSQUEDA — misma zona, entrada/stoploss específicos)
        estado_previo = None
        if supabase_service:
            existing = supabase_service.get_active_setup(
                STRATEGY_ID, symbol, entrada, stoploss
            )
            if existing:
                estado_previo = existing.get("estado")
                print(f"  Estado Previo (guardado): {estado_previo}")
            else:
                print(f"  Estado Previo: NINGUNO (nueva zona)")

        estado_historial, motivo_transicion = calcular_estado_historial(
            symbol, estado_dashboard, precio_actual,
            entrada, stoploss, tp_1_1, zona_desde, zona_hasta, estado_previo,
        )
        print(f"  Estado Historial (validado): {estado_historial}, motivo: {motivo_transicion}")

        if estado_historial == "SIN_SETUP":
            print(f"  Zona inválida para dashboard — retornando SIN SETUP")
            result = _create_sin_setup(
                precio_actual, format_trend(tendencia_h1),
                format_trend(tendencia_m15), ultimo_evento_m15,
            )
            _print_summary(result)
            return result

        print(f"\n=== LOG TRANSICION ESTADO {symbol} (H1M15) ===")
        print(f"  estado_previo: {estado_previo if estado_previo else 'NINGUNO'}")
        print(f"  estado_calculado: {estado_dashboard}")
        print(f"  estado_validado: {estado_historial}")
        print(f"  entrada: {entrada}, stoploss: {stoploss}, tp_1_1: {tp_1_1}")
        print(f"  motivo_transicion: {motivo_transicion}")
        print(f"  alineacion_h1: {motivo_alineacion}")
        print(f"================================================\n")

        result = _build_result(
            symbol, precio_actual, tendencia_h1, tendencia_m15, ultimo_evento_m15,
            zona_desde, zona_hasta, entrada, stoploss, tp_1_1,
            estado_dashboard, estado_historial, score, has_ob, has_fvg, has_barrida,
            motivo_alineacion=motivo_alineacion,
        )
        _print_summary(result)
        return result

    except Exception as e:
        print(f"  ERROR analyzing {symbol} (H1M15): {e}")
        traceback.print_exc()
        return _create_sin_setup()


# =========================
# BUILD RESULT HELPER
# =========================

def _build_result(
    symbol, precio_actual, tendencia_h1, tendencia_m15, ultimo_evento_m15,
    zona_desde, zona_hasta, entrada, stoploss, tp_1_1,
    estado_dashboard, estado_historial, score, has_ob, has_fvg, has_barrida,
    motivo_alineacion: str = "",
    estado_h1_m15_override: str = None,
) -> dict:
    """Build canonical result dict for SMC_H1_M15_PRO analysis."""
    if estado_h1_m15_override is not None:
        estado_h1_m15 = estado_h1_m15_override
    else:
        estado_h1_m15 = "ALINEADO" if motivo_alineacion else "SEGUIMIENTO"
    return {
        "symbol": symbol,
        "price": precio_actual,
        "tendencia_h1": format_trend(tendencia_h1),
        "tendencia_m15": format_trend(tendencia_m15),
        "ultimo_evento_m15": ultimo_evento_m15,
        "zona_madre_m15": {
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
        "estado_dashboard": estado_dashboard,
        "estado_historial": estado_historial,
        "estado_final": estado_historial,
        "estado": estado_historial,
        "alineacion_h1": format_trend(tendencia_h1),
        "estado_h1_m15": estado_h1_m15,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


# =========================
# ENGINE CLASS
# =========================

class SMCH1M15ProEngine(BaseStrategy):
    """SMC H1 + M15 PRO strategy engine — FASE 3A."""

    strategy_id = STRATEGY_ID
    strategy_name = STRATEGY_NAME

    def analyze(self, symbol, df_h1, df_m15, df_m1=None, **kwargs):
        return analyze_symbol_smc_h1m15_engine(symbol, df_h1, df_m15, df_m1=df_m1, **kwargs)
