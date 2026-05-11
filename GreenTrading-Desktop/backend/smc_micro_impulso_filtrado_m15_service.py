#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GreenTrading Desktop - SMC MICRO IMPULSO FILTRADO M15 Service

FILTRADO M15 delegates entirely to SMC MICRO IMPULSO normal and only adds:
  - M15 mandatory directional filter (BOOM requires ALCISTA, CRASH requires BAJISTA).
  - TP ratio 1:2 (instead of 1:1 used by the base strategy).
  - Own strategy_id / strategy_key for isolated Supabase history.

Architecture:
  1. Check M15 filter cheaply before any heavy computation.
  2. If M15 passes: call analyze_symbol_smc_micro_impulso() with sync_to_supabase=False.
     The base call runs the MICRO IMPULSO engine with Supabase access so the
     fully-tracked state (ACTIVA / LLEGANDO_A_ZONA / EN_ZONA / PROFIT / TP / SL)
     is returned — no independent state machine here.
  3. Mirror all fields from the base result.  Recalculate TP to 1:2.
  4. Sync the final result to the isolated FILTRADO history (strategy_id = STRATEGY_ID).

ISOLATION:
  - Does NOT write to SMC_MICRO_IMPULSO Supabase records.
    sync_to_supabase=False activates a read-only proxy inside
    analyze_symbol_smc_micro_impulso(): the engine can READ tracked state
    from SMC_MICRO_IMPULSO records (for correct state mirroring) but is
    completely blocked from any update_setup / create_setup on those records.
  - Only writes to SMC_MICRO_IMPULSO_FILTRADO_M15 records.
  - Zero contamination of SMC_M15_PRO, SMC_H1_M15_PRO, SMC_MICRO_IMPULSO.
"""

import traceback
from datetime import datetime, timezone

from strategies.smc_micro_impulso_filtrado_m15.engine import (
    create_sin_setup_micro_impulso_filtrado_m15_response,
    _calcular_direccion_m15,
    STRATEGY_ID,
    STRATEGY_NAME,
    STRATEGY_KEY,
)
from strategies.smc_m15_pro.engine import direccion_operativa_por_indice
from smc_micro_impulso_service import analyze_symbol_smc_micro_impulso

print("SMC_MICRO_IMPULSO_FILTRADO_M15_SERVICE_PATH:", __file__)

try:
    import supabase_service
except ImportError:
    print("WARNING: Supabase service not available for FILTRADO_M15")
    supabase_service = None

# ─── Cache de debounce (evita updates innecesarios a Supabase) ───────────────
_setup_cache_micro_impulso_filtrado_m15: dict = {}

# ─── Valores considerados "SI/verdadero" en campos ob/fvg/barrida ────────────
TRUTHY_VALUES = {"SÍ", "SI", "YES"}

# ─── Umbral de cambio de precio para disparar sync a Supabase ────────────────
PRICE_CHANGE_SYNC_THRESHOLD_PCT = 1.0  # % de cambio de precio que fuerza sync


# =============================================================================
# HELPERS
# =============================================================================

def _recalcular_tp_1_2(entrada: float, stoploss: float) -> float:
    """
    Recalcula el TP con ratio 1:2 a partir de los niveles de entrada y stoploss.

    ALCISTA (entrada > stoploss):  tp = entrada + 2 * risk
    BAJISTA (entrada < stoploss):  tp = entrada - 2 * risk
    where risk = |entrada - stoploss| = zona_size

    Args:
        entrada: Nivel de entrada del trade.
        stoploss: Nivel de stoploss del trade.

    Returns:
        TP redondeado a 2 decimales.
    """
    risk = abs(entrada - stoploss)
    if entrada > stoploss:  # ALCISTA
        return round(entrada + 2 * risk, 2)
    else:  # BAJISTA
        return round(entrada - 2 * risk, 2)


def _has_relevant_changes_filtrado_m15(symbol: str, new_data: dict) -> bool:
    """
    Debounce: devuelve True solo si cambiaron campos críticos respecto al cache.

    Args:
        symbol: Nombre del símbolo.
        new_data: Nuevos datos con campos críticos.

    Returns:
        True si hay cambios relevantes que justifiquen sincronizar con Supabase.
    """
    if symbol not in _setup_cache_micro_impulso_filtrado_m15:
        _setup_cache_micro_impulso_filtrado_m15[symbol] = new_data
        return True

    old_data = _setup_cache_micro_impulso_filtrado_m15[symbol]
    critical_fields = ["estado", "entrada", "stoploss", "tp_1_1", "score", "zona_desde", "zona_hasta"]
    for field in critical_fields:
        if old_data.get(field) != new_data.get(field):
            print(
                f"FILTRADO_M15 SYNC TRIGGER: {symbol} - {field} "
                f"cambiado de {old_data.get(field)} a {new_data.get(field)}"
            )
            _setup_cache_micro_impulso_filtrado_m15[symbol] = new_data
            return True

    old_price = old_data.get("precio_actual", 0)
    new_price = new_data.get("precio_actual", 0)
    if old_price > 0:
        pct = abs(new_price - old_price) / old_price * 100
        if pct > PRICE_CHANGE_SYNC_THRESHOLD_PCT:
            print(f"FILTRADO_M15 SYNC TRIGGER: {symbol} - precio cambio {pct:.2f}%")
            _setup_cache_micro_impulso_filtrado_m15[symbol] = new_data
            return True

    _setup_cache_micro_impulso_filtrado_m15[symbol] = new_data
    return False


# =============================================================================
# SUPABASE SYNC
# =============================================================================

def sync_setup_filtrado_m15(result: dict) -> None:
    """
    Sincroniza el setup SMC_MICRO_IMPULSO_FILTRADO_M15 con Supabase.

    Implementa:
      - Debounce (solo sincroniza si hay cambios en campos críticos).
        Excepción: estados terminales TP/SL siempre sincronizan (force_sync).
      - Guard de zonas ya cerradas (no recrea TP/SL por mismos niveles).
      - Aislamiento total por strategy_id = STRATEGY_ID.
      - NO toca registros de otras estrategias.
      - Para TP/SL: actualiza resultado, resultado_puntos y motivo_cierre.

    Args:
        result: Resultado del análisis con zona válida.
    """
    if not supabase_service:
        print("  FILTRADO_M15 SYNC: Supabase no disponible")
        return

    estado_actual = result.get("estado", "")
    estado_dashboard_actual = result.get("estado_dashboard", "")

    if estado_actual in ("SIN SETUP", "SIN_SETUP", "NO CUMPLE DIRECCIÓN M15"):
        print(f"  FILTRADO_M15 SYNC: Skip {result.get('symbol')} -- {estado_actual}")
        return

    if not result.get("entrada") or not result.get("stoploss"):
        print(f"  FILTRADO_M15 SYNC: Skip {result.get('symbol')} -- falta entrada o stoploss")
        return

    # Estados terminales: nunca deben saltarse por debounce ni por guard de PAUSADA
    terminal_state = estado_actual in ("TP", "SL") or estado_dashboard_actual in ("TP", "SL")

    symbol = result["symbol"]
    tp_val = result.get("tp") or result.get("tp_1_1")
    incoming_entrada = result.get("entrada")
    incoming_stoploss = result.get("stoploss")
    precio_actual = result.get("precio_actual") or result.get("price")

    critical_data = {
        "estado": estado_actual,
        "entrada": incoming_entrada,
        "stoploss": incoming_stoploss,
        "tp_1_1": tp_val,
        "score": result.get("score", 0),
        "zona_desde": result.get("zona_desde", 0),
        "zona_hasta": result.get("zona_hasta", 0),
        "precio_actual": precio_actual,
    }

    has_changes = _has_relevant_changes_filtrado_m15(symbol, critical_data)
    if not has_changes and not terminal_state:
        print(f"  FILTRADO_M15 SYNC: Skip {symbol} -- sin cambios relevantes")
        return

    if not has_changes and terminal_state:
        print(f"  FILTRADO_M15 SYNC: force_sync=True para {symbol} -- estado terminal {estado_actual}")

    print(f"  FILTRADO_M15 SYNC: Preparando sync para {symbol}")

    setup_data = {
        "strategy_id": STRATEGY_ID,
        "strategy_name": STRATEGY_NAME,
        "symbol": symbol,
        "tendencia_h1": "--",
        "tendencia_m15": result.get("direccion_m15", "--"),
        "ultimo_evento_m15": result.get("micro_bos_choch", "--"),
        "entrada": incoming_entrada,
        "stoploss": incoming_stoploss,
        # tp_1_1 es el nombre de columna en Supabase (schema compartido).
        # Para esta estrategia almacena el TP operativo con ratio 1:2 (no 1:1).
        "tp_1_1": tp_val,  # TP operativo 1:2 — compatibilidad schema
        "score": critical_data["score"],
        "ob": result.get("ob", "NO") in TRUTHY_VALUES,
        "fvg": result.get("fvg", "NO") in TRUTHY_VALUES,
        "barrida": result.get("barrida", "NO") in TRUTHY_VALUES,
        "estado": estado_actual,
        "estado_dashboard": estado_dashboard_actual or estado_actual,
        "precio_detectado": precio_actual,
        "precio_actual": precio_actual,
    }

    # Buscar setup activo existente (por símbolo — modo seguimiento)
    existing = None
    if hasattr(supabase_service, "get_active_setup_by_symbol"):
        existing = supabase_service.get_active_setup_by_symbol(STRATEGY_ID, symbol)

    # PAUSADA guard:
    # - En estado NO terminal: ignorar registro PAUSADA y crear uno nuevo para la
    #   zona fresca (la zona fue pausada porque llegó una zona distinta).
    # - En estado terminal TP/SL: cerrar registro PAUSADA solo si sus niveles de
    #   entrada/stoploss coinciden con los del cierre entrante; de lo contrario
    #   ignorar (no cerrar una zona vieja/distinta).
    if existing and existing.get("estado") == "PAUSADA":
        if terminal_state:
            # Para TP/SL: comprobar si los niveles coinciden con el registro PAUSADA
            existing_entrada = existing.get("entrada")
            existing_stoploss = existing.get("stoploss")
            levels_match = (
                existing_entrada is not None
                and existing_stoploss is not None
                and abs(float(existing_entrada) - float(incoming_entrada)) <= 0.01
                and abs(float(existing_stoploss) - float(incoming_stoploss)) <= 0.01
            )
            if not levels_match:
                print(
                    f"  FILTRADO_M15 SYNC: existing PAUSADA id={existing.get('id')} "
                    f"niveles no coinciden (entrada {existing_entrada} vs {incoming_entrada}, "
                    f"stoploss {existing_stoploss} vs {incoming_stoploss}) -- ignorando"
                )
                existing = None
            else:
                print(
                    f"  FILTRADO_M15 SYNC: existing PAUSADA id={existing.get('id')} "
                    f"niveles coinciden -- cerrando como {estado_actual}"
                )
        else:
            print(
                f"  FILTRADO_M15 SYNC: existing PAUSADA id={existing.get('id')} "
                f"-- ignorando, se creara nuevo registro para zona fresca"
            )
            existing = None

    # ── DEBUG LOG ────────────────────────────────────────────────────────────
    print(f"\n[FILTRADO_M15 CLOSE DEBUG]")
    print(f"  symbol: {symbol}")
    print(f"  incoming_estado: {estado_actual}")
    print(f"  incoming_estado_dashboard: {estado_dashboard_actual}")
    print(f"  incoming_entrada: {incoming_entrada}")
    print(f"  incoming_stoploss: {incoming_stoploss}")
    print(f"  incoming_tp: {tp_val}")
    print(f"  incoming_precio: {precio_actual}")
    print(f"  existing_id: {existing.get('id') if existing else None}")
    print(f"  existing_estado: {existing.get('estado') if existing else None}")
    print(f"  existing_entrada: {existing.get('entrada') if existing else None}")
    print(f"  existing_stoploss: {existing.get('stoploss') if existing else None}")
    # ─────────────────────────────────────────────────────────────────────────

    if existing:
        setup_id = existing["id"]
        updates = {
            "estado": estado_actual,
            "estado_dashboard": setup_data["estado_dashboard"],
            "precio_actual": precio_actual,
        }
        if terminal_state:
            # Calcular resultado_puntos: positivo para TP, negativo para SL
            tp_puntos = result.get("tp_puntos")
            sl_puntos = result.get("sl_puntos")
            if estado_actual == "TP":
                resultado_puntos = tp_puntos if tp_puntos is not None else None
                motivo_cierre = "TP alcanzado"
            else:  # SL
                resultado_puntos = -sl_puntos if sl_puntos is not None else None
                motivo_cierre = "SL alcanzado"
            updates["resultado"] = estado_actual
            if resultado_puntos is not None:
                updates["resultado_puntos"] = resultado_puntos
            updates["motivo_cierre"] = motivo_cierre

        print(f"  [FILTRADO_M15 CLOSE DEBUG] action=UPDATE_CLOSE" if terminal_state else f"  [FILTRADO_M15 CLOSE DEBUG] action=UPDATE")
        print(f"  FILTRADO_M15 SYNC: UPDATE id={setup_id}, estado={estado_actual}")
        res = supabase_service.update_setup(setup_id, updates)
        if res:
            print(f"FILTRADO_M15 SYNC OK: Updated {symbol}")
        else:
            print(f"FILTRADO_M15 SYNC WARN: update devolvio None para {symbol}")
    else:
        # Para estados terminales sin registro existente: no crear registro nuevo
        if terminal_state:
            print(f"  [FILTRADO_M15 CLOSE DEBUG] action=SKIP -- no hay registro activo para cerrar")
            print(
                f"  FILTRADO_M15 SYNC: SKIP {symbol} -- "
                f"estado terminal {estado_actual} sin registro activo para cerrar"
            )
            return

        print(f"  [FILTRADO_M15 CLOSE DEBUG] action=CREATE")

        # Guard: no recrear zonas ya cerradas con los mismos niveles
        closed_setup = None
        if (
            hasattr(supabase_service, "get_closed_setup_by_levels")
            and critical_data.get("tp_1_1") is not None
        ):
            closed_setup = supabase_service.get_closed_setup_by_levels(
                STRATEGY_ID,
                symbol,
                incoming_entrada,
                incoming_stoploss,
                critical_data["tp_1_1"],
            )

        decision = "SKIP_ALREADY_CLOSED" if closed_setup else "CREATE_NEW"
        print(f"\nFILTRADO_M15 DUPLICATE_CLOSED_ZONE_CHECK:")
        print(f"  symbol: {symbol}")
        print(f"  estrategia: {STRATEGY_ID}")
        print(f"  entrada: {incoming_entrada}")
        print(f"  stoploss: {incoming_stoploss}")
        print(f"  tp operativo (1:2): {critical_data['tp_1_1']}")  # tp_1_1 = TP 1:2 por compat schema
        print(f"  found_closed: {bool(closed_setup)}")
        print(f"  decision: {decision}")

        if closed_setup:
            # Zona ya cerrada — resetear a SIN_SETUP
            sin_setup = create_sin_setup_micro_impulso_filtrado_m15_response(
                symbol=symbol, price=precio_actual
            )
            for k, v in sin_setup.items():
                result[k] = v
            _setup_cache_micro_impulso_filtrado_m15[symbol] = {
                "estado": "SIN_SETUP",
                "entrada": None,
                "stoploss": None,
                "tp_1_1": None,
                "score": 0,
                "zona_desde": 0,
                "zona_hasta": 0,
                "precio_actual": precio_actual,
            }
            print(f"  FILTRADO_M15 SYNC: SKIP -- zona ya cerrada (TP/SL)")
            return

        res = supabase_service.create_setup(setup_data)
        if res:
            print(f"FILTRADO_M15 SYNC OK: Created setup {symbol} id={res.get('id')}")
        else:
            print(f"FILTRADO_M15 SYNC WARN: create_setup devolvio None para {symbol}")


# =============================================================================
# MAIN ANALYZE FUNCTION
# =============================================================================

def analyze_symbol_smc_micro_impulso_filtrado_m15(
    symbol: str,
    df_m1=None,
    df_m15=None,
) -> dict:
    """
    Analiza un símbolo con la estrategia SMC MICRO IMPULSO FILTRADO M15.

    Delega completamente en SMC MICRO IMPULSO normal para obtener el estado
    completamente trackeado (ACTIVA / LLEGANDO_A_ZONA / EN_ZONA / PROFIT / TP / SL),
    luego aplica el filtro M15 obligatorio y recalcula el TP a ratio 1:2.

    Garantía: para cada símbolo donde M15 cumple, todos los campos operativos
    (estado, zona_desde, zona_hasta, entrada, stoploss, score, ob, fvg, barrida,
    desplazamiento, micro_bos_choch, precio_actual) son IDÉNTICOS a los de
    /api/smc/micro-impulso/snapshot.  La única diferencia es el TP (1:2 aquí,
    1:1 en MICRO IMPULSO normal).

    Args:
        symbol: Symbol name (e.g. "Boom 1000 Index").
        df_m1: DataFrame con velas M1 (núcleo operativo).
        df_m15: DataFrame con velas M15 (filtro direccional obligatorio).

    Returns:
        dict con snapshot completo de la estrategia.
    """
    try:
        # Precio para fallback en caso de error
        price = None
        if df_m1 is not None and len(df_m1) > 0:
            try:
                price = float(df_m1.iloc[-1]["close"])
            except Exception:
                pass

        def _sin_setup(motivo, direccion_indice="--", direccion_m15="--",
                       cumple_m15=False, estado="SIN SETUP"):
            return create_sin_setup_micro_impulso_filtrado_m15_response(
                symbol=symbol, price=price,
                direccion_indice=direccion_indice,
                direccion_m15=direccion_m15,
                cumple_m15=cumple_m15,
                motivo=motivo,
                estado=estado,
            )

        # ------------------------------------------------------------------
        # 1. Dirección operativa del índice (Boom → ALCISTA, Crash → BAJISTA)
        # ------------------------------------------------------------------
        direccion_indice = direccion_operativa_por_indice(symbol)
        if not direccion_indice:
            print(f"  FILTRADO_M15: {symbol} no es Boom ni Crash -> SIN SETUP")
            return _sin_setup("SÍMBOLO NO CLASIFICADO")

        # ------------------------------------------------------------------
        # 2. Dirección estructural M15
        # ------------------------------------------------------------------
        if df_m15 is None or len(df_m15) == 0:
            print(f"  FILTRADO_M15: sin datos M15 para {symbol} -> SIN SETUP")
            return _sin_setup("SIN DATOS M15", direccion_indice=direccion_indice)

        direccion_m15 = _calcular_direccion_m15(df_m15)

        # ------------------------------------------------------------------
        # 3. Aplicar filtro M15 obligatorio
        # ------------------------------------------------------------------
        cumple_m15 = (direccion_m15 != "--") and (direccion_m15 == direccion_indice)
        if not cumple_m15:
            motivo_nc = (
                f"M15={direccion_m15} != INDICE={direccion_indice}"
                if direccion_m15 != "--"
                else "DIRECCIÓN M15 INDETERMINADA"
            )
            print(f"  FILTRADO_M15: NO CUMPLE M15 para {symbol}: {motivo_nc}")
            return _sin_setup(
                motivo=motivo_nc,
                direccion_indice=direccion_indice,
                direccion_m15=direccion_m15,
                cumple_m15=False,
                estado="NO CUMPLE DIRECCIÓN M15",
            )

        print(f"  FILTRADO_M15: CUMPLE M15 {direccion_m15} == {direccion_indice} para {symbol}")

        # ------------------------------------------------------------------
        # 4. Obtener resultado completamente trackeado de MICRO IMPULSO normal.
        #    sync_to_supabase=False activa el modo read-only:
        #    - el engine PUEDE leer registros SMC_MICRO_IMPULSO (para tracking)
        #    - el engine NO PUEDE escribir/actualizar esos registros
        #    → cero contaminación del historial SMC_MICRO_IMPULSO.
        # ------------------------------------------------------------------
        base = analyze_symbol_smc_micro_impulso(
            symbol, df_m1, df_m15, sync_to_supabase=False
        )

        base_estado = base.get("estado", "SIN SETUP")
        if base_estado in ("SIN SETUP", "SIN_SETUP"):
            print(f"  FILTRADO_M15: base MICRO IMPULSO sin setup para {symbol}")
            return _sin_setup(
                "SIN SETUP EN MICRO IMPULSO BASE",
                direccion_indice=direccion_indice,
                direccion_m15=direccion_m15,
                cumple_m15=True,
            )

        # ------------------------------------------------------------------
        # 5. Extraer niveles de zona del resultado base
        # ------------------------------------------------------------------
        zona_madre = base.get("zona_madre_m1", {})
        zona_desde = float(zona_madre.get("desde", 0) or 0)
        zona_hasta = float(zona_madre.get("hasta", 0) or 0)
        zona_size = abs(zona_hasta - zona_desde)

        entrada = base.get("entrada")
        stoploss = base.get("stoploss")

        if entrada is None or stoploss is None:
            print(f"  FILTRADO_M15: base sin entrada/stoploss para {symbol}")
            return _sin_setup(
                "NIVELES INCOMPLETOS EN BASE",
                direccion_indice=direccion_indice,
                direccion_m15=direccion_m15,
                cumple_m15=True,
            )

        # ------------------------------------------------------------------
        # 6. Recalcular TP con ratio 1:2 (única diferencia operativa)
        # ------------------------------------------------------------------
        tp_1_2 = _recalcular_tp_1_2(entrada, stoploss)
        tp_puntos = abs(tp_1_2 - entrada)
        sl_puntos = abs(stoploss - entrada)

        # ------------------------------------------------------------------
        # 7. Construir resultado FILTRADO M15:
        #    todos los campos operativos vienen del resultado base ya trackeado,
        #    solo se sobreescriben strategy_id/key, TP y campos de filtro M15.
        # ------------------------------------------------------------------
        estado = base.get("estado", "ACTIVA")
        estado_dashboard = base.get("estado_dashboard", estado)
        estado_historial = base.get("estado_historial", estado)
        estado_final = base.get("estado_final", estado_historial)

        precio_actual = base.get("price") or price
        now = datetime.now(timezone.utc).isoformat()
        updated_at = base.get("updated_at", now)

        result = {
            "symbol": symbol,
            "estrategia": STRATEGY_NAME,
            "strategy_key": STRATEGY_KEY,
            "price": precio_actual,
            "precio_actual": precio_actual,
            "direccion_indice": direccion_indice,
            "direccion_m15": direccion_m15,
            "cumple_m15": True,
            "micro_bos_choch": base.get("micro_bos_choch", "--"),
            "zona_desde": round(zona_desde, 2),
            "zona_hasta": round(zona_hasta, 2),
            "zona_size": round(zona_size, 4),
            "entrada": round(entrada, 2),
            "stoploss": round(stoploss, 2),
            # tp_1_1: nombre de columna en Supabase (schema compartido).
            # Almacena el TP operativo 1:2 — diferencia vs MICRO IMPULSO 1:1.
            "tp": tp_1_2,
            "tp_1_1": tp_1_2,
            "tp_operativo": tp_1_2,
            "tp_ratio": 2,
            "sl": round(stoploss, 2),
            "score": base.get("score", 0),
            "ob": base.get("ob", "NO"),
            "fvg": base.get("fvg", "NO"),
            "barrida": base.get("barrida", "NO"),
            # MICRO IMPULSO normal uses the field name "desplazamiento_valido" (SI/NO).
            # FILTRADO M15 (and its Supabase schema) uses "desplazamiento" (SI/NO).
            # Both hold the same value; this explicit mapping bridges the name gap.
            "desplazamiento": base.get("desplazamiento_valido", "NO"),
            "estado": estado,
            "estado_dashboard": estado_dashboard,
            "estado_historial": estado_historial,
            "estado_final": estado_final,
            "tp_puntos": round(tp_puntos, 4),
            "sl_puntos": round(sl_puntos, 4),
            "timestamp": updated_at,
            "updated_at": updated_at,
        }

        print(
            f"  FILTRADO_M15 {symbol}: estado={estado} "
            f"entrada={result['entrada']} sl={result['stoploss']} tp={tp_1_2}"
        )

        # ------------------------------------------------------------------
        # 8. Sincronizar con historial propio (strategy_id = STRATEGY_ID)
        # ------------------------------------------------------------------
        if (
            estado not in ("SIN SETUP", "SIN_SETUP", "NO CUMPLE DIRECCIÓN M15")
            and result.get("entrada") is not None
            and result.get("stoploss") is not None
        ):
            sync_setup_filtrado_m15(result)

        return result

    except Exception as e:
        print(f"MICRO_IMPULSO_FILTRADO_M15 ERROR: {symbol} - {e}")
        traceback.print_exc()
        fallback_price = None
        if df_m1 is not None and len(df_m1) > 0:
            try:
                fallback_price = float(df_m1.iloc[-1]["close"])
            except Exception:
                pass
        return create_sin_setup_micro_impulso_filtrado_m15_response(
            symbol=symbol, price=fallback_price
        )

