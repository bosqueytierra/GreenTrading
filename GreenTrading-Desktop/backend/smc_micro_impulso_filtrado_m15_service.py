#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GreenTrading Desktop - SMC MICRO IMPULSO FILTRADO M15 Service

Parte 3: Gestión operativa completa.

Añade al motor de Parte 2:
  - Máquina de estados: ACTIVA → EN_ZONA → PROFIT → TP/SL
  - PROFIT ↔ EN_ZONA (precio puede volver a zona antes de TP)
  - PAUSADA cuando nueva zona aparece mientras existe una ACTIVA
  - DESCARTADA solo para datos corruptos / zonas imposibles
  - Modo seguimiento en tiempo real con Supabase
  - Historial independiente (strategy_id = 'SMC_MICRO_IMPULSO_FILTRADO_M15')
  - TP ratio 1:2, filtro M15 obligatorio, micro zonas M1

AISLAMIENTO TOTAL:
  - No modifica SMC_M15_PRO, SMC_H1_M15_PRO, SMC_MICRO_IMPULSO.
  - Cache, historial y sync propios.
  - strategy_key = 'microimpulso_filtrado_m15'
"""

import traceback
from datetime import datetime, timezone

from strategies.smc_micro_impulso_filtrado_m15.engine import (
    SMCMicroImpulsoFiltradoM15Engine,
    create_sin_setup_micro_impulso_filtrado_m15_response,
    STRATEGY_ID,
    STRATEGY_NAME,
    STRATEGY_KEY,
)
from core.state_machine import (
    calcular_estado_dashboard,
    calcular_transicion_estado,
)

print("SMC_MICRO_IMPULSO_FILTRADO_M15_SERVICE_PATH:", __file__)

try:
    import supabase_service
except ImportError:
    print("WARNING: Supabase service not available for FILTRADO_M15")
    supabase_service = None

# ─── Instancia del engine ────────────────────────────────────────────────────
_engine = SMCMicroImpulsoFiltradoM15Engine()

# ─── Cache de debounce (evita updates innecesarios a Supabase) ───────────────
_setup_cache_micro_impulso_filtrado_m15: dict = {}

# ─── Cache de tracking en memoria (fallback cuando Supabase no disponible) ───
_tracking_cache_filtrado_m15: dict = {}

# ─── Valores considerados "SI/verdadero" en campos ob/fvg/barrida ────────────
TRUTHY_VALUES = {"SÍ", "SI", "YES"}

# ─── Estados terminales: no se cambian una vez alcanzados ────────────────────
TERMINAL_STATES = {"TP", "SL", "DESCARTADA"}

# ─── Estados "en operación activa": el trade ya tocó la zona ─────────────────
IN_TRADE_STATES = {"EN_ZONA", "PROFIT"}

# ─── Umbral de diferencia de niveles para detectar zona nueva ────────────────
ZONE_LEVEL_TOLERANCE = 0.01   # puntos — umbral absoluto para comparar entradas/SL

# ─── Umbral de cambio de precio para disparar sync a Supabase ────────────────
PRICE_CHANGE_SYNC_THRESHOLD_PCT = 1.0  # % de cambio de precio que fuerza sync


# =============================================================================
# HELPERS
# =============================================================================

def _derivar_zona(entrada: float, stoploss: float):
    """
    Deriva zona_desde, zona_hasta y dirección desde entrada y stoploss.

    Convención del engine:
      ALCISTA: entrada = zona_hasta (borde superior)  >  stoploss = zona_desde (borde inferior)
      BAJISTA: entrada = zona_desde (borde inferior)  <  stoploss = zona_hasta (borde superior)

    Raises:
        ValueError: Si entrada == stoploss (zona de tamaño cero, zona imposible).

    Returns:
        (zona_desde, zona_hasta, direccion)
    """
    if entrada == stoploss:
        raise ValueError(
            f"_derivar_zona: entrada == stoploss ({entrada}) — zona de tamaño cero es inválida"
        )
    if entrada > stoploss:
        return stoploss, entrada, "ALCISTA"
    return entrada, stoploss, "BAJISTA"


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
            print(f"FILTRADO_M15 SYNC TRIGGER: {symbol} - precio cambió {pct:.2f}%")
            _setup_cache_micro_impulso_filtrado_m15[symbol] = new_data
            return True

    _setup_cache_micro_impulso_filtrado_m15[symbol] = new_data
    return False


def _bool_to_si_no(val) -> str:
    """Normaliza bool/str a 'SI'/'NO'."""
    if isinstance(val, bool):
        return "SI" if val else "NO"
    if isinstance(val, str):
        return "SI" if val in TRUTHY_VALUES else "NO"
    return "NO"


def _build_result_tracked(
    symbol: str,
    tracked: dict,
    fresh_result: dict,
    estado_nuevo: str,
    motivo: str,
) -> dict:
    """
    Construye el resultado del snapshot usando la zona guardada (tracking)
    y el estado nuevo calculado por la máquina de estados.

    Preserva los niveles de zona originales del setup guardado.
    Actualiza precio_actual, estado y contexto de mercado desde fresh_result.

    Args:
        symbol: Nombre del símbolo.
        tracked: Registro del setup guardado (dict de Supabase o cache).
        fresh_result: Resultado fresco del engine (precio actual, dirección M15).
        estado_nuevo: Estado calculado por la máquina de estados.
        motivo: Motivo de la transición.

    Returns:
        dict con snapshot completo listo para el dashboard.
    """
    now = datetime.now(timezone.utc).isoformat()

    entrada = tracked.get("entrada")
    stoploss = tracked.get("stoploss")
    tp = tracked.get("tp_1_1") or tracked.get("tp")
    precio_actual = fresh_result.get("precio_actual") or fresh_result.get("price")

    zona_desde, zona_hasta, _ = _derivar_zona(entrada, stoploss)
    zona_size = abs(zona_hasta - zona_desde)

    # Contexto de mercado desde fresh_result (siempre actualizado)
    direccion_indice = fresh_result.get("direccion_indice", "--")
    direccion_m15 = fresh_result.get("direccion_m15", "--")
    cumple_m15 = fresh_result.get("cumple_m15", False)

    # Campos del setup original (guardados en tracking)
    micro_bos_choch = (
        tracked.get("micro_bos_choch")
        or tracked.get("ultimo_evento_m15")
        or "--"
    )
    score = tracked.get("score", 0)
    ob = _bool_to_si_no(tracked.get("ob", "NO"))
    fvg = _bool_to_si_no(tracked.get("fvg", "NO"))
    barrida = _bool_to_si_no(tracked.get("barrida", "NO"))
    desplazamiento = _bool_to_si_no(tracked.get("desplazamiento", "NO"))

    tp_puntos = abs(tp - entrada) if tp is not None and entrada is not None else 0.0
    sl_puntos = abs(stoploss - entrada) if stoploss is not None and entrada is not None else 0.0

    return {
        "symbol": symbol,
        "estrategia": STRATEGY_NAME,
        "strategy_key": STRATEGY_KEY,
        "price": precio_actual,
        "precio_actual": precio_actual,
        "direccion_indice": direccion_indice,
        "direccion_m15": direccion_m15,
        "cumple_m15": cumple_m15,
        "micro_bos_choch": micro_bos_choch,
        "zona_desde": round(zona_desde, 2),
        "zona_hasta": round(zona_hasta, 2),
        "zona_size": round(zona_size, 4),
        "entrada": round(entrada, 2),
        "stoploss": round(stoploss, 2),
        # tp_1_1 mantiene compatibilidad con el schema de Supabase (columna compartida).
        # Para esta estrategia, tp_1_1 almacena el TP operativo 1:2 (no 1:1).
        # Usar tp_operativo o tp para lógica interna; tp_ratio indica el ratio real.
        "tp": round(tp, 2) if tp is not None else None,
        "tp_1_1": round(tp, 2) if tp is not None else None,  # TP operativo 1:2 — nombre heredado de schema Supabase
        "tp_operativo": round(tp, 2) if tp is not None else None,  # Alias explícito
        "tp_ratio": 2,  # Ratio real de esta estrategia: 1:2 (no 1:1)
        "sl": round(stoploss, 2),
        "score": score,
        "ob": ob,
        "fvg": fvg,
        "barrida": barrida,
        "desplazamiento": desplazamiento,
        "estado": estado_nuevo,
        "motivo": motivo,
        "estado_dashboard": estado_nuevo,
        "estado_historial": estado_nuevo,
        "estado_final": estado_nuevo,
        "tp_puntos": round(tp_puntos, 4),
        "sl_puntos": round(sl_puntos, 4),
        "timestamp": now,
        "updated_at": now,
    }


# =============================================================================
# SUPABASE SYNC
# =============================================================================

def _update_estado_supabase_filtrado_m15(
    setup_id: int,
    estado_nuevo: str,
    precio_actual: float,
) -> None:
    """
    Actualiza solo el estado de un setup existente en Supabase.

    Args:
        setup_id: ID del registro en Supabase.
        estado_nuevo: Nuevo estado a guardar.
        precio_actual: Precio actual para registrar en updated_at.
    """
    if not supabase_service or setup_id is None:
        return
    updates = {
        "estado": estado_nuevo,
        "estado_dashboard": estado_nuevo,
        "precio_actual": precio_actual,
    }
    print(f"  FILTRADO_M15: Actualizando id={setup_id} → {estado_nuevo}")
    supabase_service.update_setup(setup_id, updates)


def sync_setup_filtrado_m15(result: dict) -> None:
    """
    Sincroniza el setup SMC_MICRO_IMPULSO_FILTRADO_M15 con Supabase.

    Implementa:
      - Debounce (solo sincroniza si hay cambios en campos críticos).
      - Guard de zonas ya cerradas (no recrea TP/SL por mismos niveles).
      - Aislamiento total por strategy_id = STRATEGY_ID.
      - NO toca registros de otras estrategias.

    Args:
        result: Resultado del análisis con zona válida.
    """
    if not supabase_service:
        print("  FILTRADO_M15 SYNC: Supabase no disponible")
        return

    estado_actual = result.get("estado", "")
    if estado_actual in ("SIN SETUP", "SIN_SETUP", "NO CUMPLE DIRECCIÓN M15"):
        print(f"  FILTRADO_M15 SYNC: Skip {result.get('symbol')} — {estado_actual}")
        return

    if not result.get("entrada") or not result.get("stoploss"):
        print(f"  FILTRADO_M15 SYNC: Skip {result.get('symbol')} — falta entrada o stoploss")
        return

    symbol = result["symbol"]
    tp_val = result.get("tp") or result.get("tp_1_1")
    estado_historial = result.get("estado_historial", result.get("estado_dashboard", "ACTIVA"))

    critical_data = {
        "estado": estado_historial,
        "entrada": result.get("entrada"),
        "stoploss": result.get("stoploss"),
        "tp_1_1": tp_val,
        "score": result.get("score", 0),
        "zona_desde": result.get("zona_desde", 0),
        "zona_hasta": result.get("zona_hasta", 0),
        "precio_actual": result.get("precio_actual") or result.get("price"),
    }

    if not _has_relevant_changes_filtrado_m15(symbol, critical_data):
        print(f"  FILTRADO_M15 SYNC: Skip {symbol} — sin cambios relevantes")
        return

    print(f"  FILTRADO_M15 SYNC: Preparando sync para {symbol}")

    setup_data = {
        "strategy_id": STRATEGY_ID,
        "strategy_name": STRATEGY_NAME,
        "symbol": symbol,
        "tendencia_h1": "--",
        "tendencia_m15": result.get("direccion_m15", "--"),
        "ultimo_evento_m15": result.get("micro_bos_choch", "--"),
        "entrada": critical_data["entrada"],
        "stoploss": critical_data["stoploss"],
        # tp_1_1 es el nombre de columna en Supabase (schema compartido).
        # Para esta estrategia almacena el TP operativo con ratio 1:2 (no 1:1).
        "tp_1_1": critical_data["tp_1_1"],  # TP operativo 1:2 — compatibilidad schema
        "score": critical_data["score"],
        "ob": result.get("ob", "NO") in TRUTHY_VALUES,
        "fvg": result.get("fvg", "NO") in TRUTHY_VALUES,
        "barrida": result.get("barrida", "NO") in TRUTHY_VALUES,
        "estado": critical_data["estado"],
        "estado_dashboard": result.get("estado_dashboard", "ACTIVA"),
        "precio_detectado": critical_data["precio_actual"],
        "precio_actual": critical_data["precio_actual"],
    }

    # Buscar setup activo existente (por símbolo — modo seguimiento)
    existing = None
    if hasattr(supabase_service, "get_active_setup_by_symbol"):
        existing = supabase_service.get_active_setup_by_symbol(STRATEGY_ID, symbol)

    if existing:
        setup_id = existing["id"]
        updates = {
            "estado": setup_data["estado"],
            "estado_dashboard": setup_data["estado_dashboard"],
            "precio_actual": setup_data["precio_actual"],
        }
        print(f"  FILTRADO_M15 SYNC: UPDATE id={setup_id}, estado={setup_data['estado']}")
        res = supabase_service.update_setup(setup_id, updates)
        if res:
            print(f"FILTRADO_M15 SYNC OK: Updated {symbol}")
        else:
            print(f"FILTRADO_M15 SYNC WARN: update devolvió None para {symbol}")
    else:
        # Guard: no recrear zonas ya cerradas con los mismos niveles
        closed_setup = None
        if (
            hasattr(supabase_service, "get_closed_setup_by_levels")
            and critical_data.get("tp_1_1") is not None
        ):
            closed_setup = supabase_service.get_closed_setup_by_levels(
                STRATEGY_ID,
                symbol,
                critical_data["entrada"],
                critical_data["stoploss"],
                critical_data["tp_1_1"],
            )

        decision = "SKIP_ALREADY_CLOSED" if closed_setup else "CREATE_NEW"
        print(f"\nFILTRADO_M15 DUPLICATE_CLOSED_ZONE_CHECK:")
        print(f"  symbol: {symbol}")
        print(f"  estrategia: {STRATEGY_ID}")
        print(f"  entrada: {critical_data['entrada']}")
        print(f"  stoploss: {critical_data['stoploss']}")
        print(f"  tp operativo (1:2): {critical_data['tp_1_1']}")  # tp_1_1 = TP 1:2 por compat schema
        print(f"  found_closed: {bool(closed_setup)}")
        print(f"  decision: {decision}")

        if closed_setup:
            # Zona ya cerrada — resetear a SIN_SETUP
            sin_setup = create_sin_setup_micro_impulso_filtrado_m15_response(
                symbol=symbol, price=critical_data["precio_actual"]
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
                "precio_actual": critical_data["precio_actual"],
            }
            if symbol in _tracking_cache_filtrado_m15:
                del _tracking_cache_filtrado_m15[symbol]
            print(f"  FILTRADO_M15 SYNC: SKIP — zona ya cerrada (TP/SL)")
            return

        res = supabase_service.create_setup(setup_data)
        if res:
            print(f"FILTRADO_M15 SYNC OK: Created setup {symbol} id={res.get('id')}")
        else:
            print(f"FILTRADO_M15 SYNC WARN: create_setup devolvió None para {symbol}")


# =============================================================================
# MODO SEGUIMIENTO — TRACKING STATE MACHINE
# =============================================================================

def _modo_seguimiento_filtrado_m15(
    symbol: str,
    fresh_result: dict,
    df_m1=None,
) -> dict:
    """
    Aplica el modo seguimiento sobre el resultado fresco del engine.

    Transiciones soportadas:
      ACTIVA → EN_ZONA → PROFIT → TP   (camino ganador)
      ACTIVA → EN_ZONA → SL            (camino perdedor)
      PROFIT ↔ EN_ZONA                 (precio vuelve a zona antes de TP)
      ACTIVA → PAUSADA                 (nueva zona detectada, se pausa la vieja)

    Prioridad de operaciones:
      1. Si existe trade EN_ZONA o PROFIT → NO reemplazar con zona nueva.
      2. Si ACTIVA y llega zona diferente → PAUSAR antigua, usar nueva.
      3. PAUSADA se trata como "sin tracking" — fresh_result toma el control.
      4. Sin setup activo → fresh_result se usa directamente.

    Args:
        symbol: Nombre del símbolo.
        fresh_result: Resultado fresco del engine (análisis de mercado actual).
        df_m1: DataFrame M1 para calcular velocidad hacia zona (opcional).

    Returns:
        dict con snapshot final (puede ser fresh o tracked según contexto).
    """
    precio_actual = fresh_result.get("precio_actual") or fresh_result.get("price")
    fresh_estado = fresh_result.get("estado", "SIN SETUP")

    # ── Intentar obtener setup activo desde Supabase ─────────────────────────
    existing = None
    if supabase_service and hasattr(supabase_service, "get_active_setup_by_symbol"):
        try:
            existing = supabase_service.get_active_setup_by_symbol(STRATEGY_ID, symbol)
        except Exception as exc:
            print(f"  FILTRADO_M15 TRACKING: Error querying Supabase — {exc}")
            existing = None

    # ── Fallback: usar tracking en memoria si Supabase no disponible ──────────
    if existing is None and symbol in _tracking_cache_filtrado_m15:
        cached = _tracking_cache_filtrado_m15[symbol]
        if cached.get("estado") not in TERMINAL_STATES:
            existing = cached
            print(f"  FILTRADO_M15 TRACKING: Usando cache en memoria para {symbol}")

    # ── Sin setup activo → usar fresh directamente ────────────────────────────
    if not existing:
        print(f"  FILTRADO_M15 TRACKING: Sin setup activo → resultado fresco")
        if fresh_estado == "ACTIVA" and fresh_result.get("entrada") is not None:
            _tracking_cache_filtrado_m15[symbol] = {
                "estado": "ACTIVA",
                "entrada": fresh_result.get("entrada"),
                "stoploss": fresh_result.get("stoploss"),
                "tp_1_1": fresh_result.get("tp"),
                "score": fresh_result.get("score", 0),
                "ob": fresh_result.get("ob", "NO"),
                "fvg": fresh_result.get("fvg", "NO"),
                "barrida": fresh_result.get("barrida", "NO"),
                "desplazamiento": fresh_result.get("desplazamiento", "NO"),
                "micro_bos_choch": fresh_result.get("micro_bos_choch", "--"),
                "precio_actual": precio_actual,
            }
        return fresh_result

    estado_previo = existing.get("estado", "ACTIVA")

    # ── PAUSADA se trata como "sin tracking activo" ───────────────────────────
    # La zona fue pausada porque llegó una zona nueva; fresh_result toma control.
    if estado_previo == "PAUSADA":
        print(f"  FILTRADO_M15 TRACKING: Estado PAUSADA → fresh_result toma control")
        if fresh_estado == "ACTIVA" and fresh_result.get("entrada") is not None:
            _tracking_cache_filtrado_m15[symbol] = {
                "estado": "ACTIVA",
                "entrada": fresh_result.get("entrada"),
                "stoploss": fresh_result.get("stoploss"),
                "tp_1_1": fresh_result.get("tp"),
                "score": fresh_result.get("score", 0),
                "ob": fresh_result.get("ob", "NO"),
                "fvg": fresh_result.get("fvg", "NO"),
                "barrida": fresh_result.get("barrida", "NO"),
                "desplazamiento": fresh_result.get("desplazamiento", "NO"),
                "micro_bos_choch": fresh_result.get("micro_bos_choch", "--"),
                "precio_actual": precio_actual,
            }
        return fresh_result

    entrada_g = existing.get("entrada")
    stoploss_g = existing.get("stoploss")
    tp_g = existing.get("tp_1_1") or existing.get("tp")

    # Validar datos mínimos del setup guardado
    if not entrada_g or not stoploss_g or not tp_g:
        print(f"  FILTRADO_M15 TRACKING: Setup guardado incompleto → fresco")
        return fresh_result

    if precio_actual is None:
        print(f"  FILTRADO_M15 TRACKING: Sin precio_actual → fresco")
        return fresh_result

    zona_desde_g, zona_hasta_g, direccion_g = _derivar_zona(entrada_g, stoploss_g)

    print(f"\nFILTRADO_M15 TRACKING: {symbol}")
    print(f"  estado_previo: {estado_previo}")
    print(f"  precio_actual: {precio_actual}")
    print(f"  entrada_guardada: {entrada_g}")
    print(f"  stoploss_guardado: {stoploss_g}")
    print(f"  tp_guardado: {tp_g}")
    print(f"  zona: [{zona_desde_g}, {zona_hasta_g}] dir={direccion_g}")

    # ─────────────────────────────────────────────────────────────────────────
    # CASO A: EN_ZONA o PROFIT — operación activa — NO reemplazar con zona nueva
    # ─────────────────────────────────────────────────────────────────────────
    if estado_previo in IN_TRADE_STATES:
        print(f"  FILTRADO_M15 TRACKING: Trade activo ({estado_previo}) — aplicando SM")

        estado_dashboard = calcular_estado_dashboard(
            precio_actual=precio_actual,
            entrada=entrada_g,
            zona_desde=zona_desde_g,
            zona_hasta=zona_hasta_g,
            direccion=direccion_g,
            df_m1=df_m1,
            symbol=symbol,
        )

        estado_nuevo, motivo = calcular_transicion_estado(
            symbol=symbol,
            estado_previo=estado_previo,
            estado_calculado=estado_dashboard,
            precio_actual=precio_actual,
            entrada=entrada_g,
            stoploss=stoploss_g,
            tp=tp_g,
            zona_desde=zona_desde_g,
            zona_hasta=zona_hasta_g,
        )

        print(f"  FILTRADO_M15 TRACKING: {estado_previo} → {estado_nuevo} | {motivo}")

        if estado_nuevo != estado_previo:
            _update_estado_supabase_filtrado_m15(existing.get("id"), estado_nuevo, precio_actual)
        if symbol in _tracking_cache_filtrado_m15:
            _tracking_cache_filtrado_m15[symbol]["estado"] = estado_nuevo
            _tracking_cache_filtrado_m15[symbol]["precio_actual"] = precio_actual

        return _build_result_tracked(symbol, existing, fresh_result, estado_nuevo, motivo)

    # ─────────────────────────────────────────────────────────────────────────
    # CASO B: ACTIVA — posible reemplazo de zona si llega una zona diferente
    # ─────────────────────────────────────────────────────────────────────────
    if estado_previo == "ACTIVA":
        fresh_has_zone = (
            fresh_estado == "ACTIVA"
            and fresh_result.get("entrada") is not None
            and fresh_result.get("stoploss") is not None
        )

        if fresh_has_zone:
            fresh_entrada = fresh_result.get("entrada")
            fresh_stoploss = fresh_result.get("stoploss")

            is_different = (
                abs(fresh_entrada - entrada_g) > ZONE_LEVEL_TOLERANCE
                or abs(fresh_stoploss - stoploss_g) > ZONE_LEVEL_TOLERANCE
            )

            if is_different:
                # Nueva zona diferente → PAUSAR antigua, activar nueva
                print(f"  FILTRADO_M15 TRACKING: Nueva zona diferente → PAUSANDO {symbol}")
                _update_estado_supabase_filtrado_m15(existing.get("id"), "PAUSADA", precio_actual)
                # Limpiar cache para que fresh_result arranque desde cero
                if symbol in _tracking_cache_filtrado_m15:
                    del _tracking_cache_filtrado_m15[symbol]
                # Inicializar cache con nueva zona
                _tracking_cache_filtrado_m15[symbol] = {
                    "estado": "ACTIVA",
                    "entrada": fresh_entrada,
                    "stoploss": fresh_stoploss,
                    "tp_1_1": fresh_result.get("tp"),
                    "score": fresh_result.get("score", 0),
                    "ob": fresh_result.get("ob", "NO"),
                    "fvg": fresh_result.get("fvg", "NO"),
                    "barrida": fresh_result.get("barrida", "NO"),
                    "desplazamiento": fresh_result.get("desplazamiento", "NO"),
                    "micro_bos_choch": fresh_result.get("micro_bos_choch", "--"),
                    "precio_actual": precio_actual,
                }
                return fresh_result

        # Misma zona (o sin zona fresca) → aplicar máquina de estados sobre zona guardada
        estado_dashboard = calcular_estado_dashboard(
            precio_actual=precio_actual,
            entrada=entrada_g,
            zona_desde=zona_desde_g,
            zona_hasta=zona_hasta_g,
            direccion=direccion_g,
            df_m1=df_m1,
            symbol=symbol,
        )

        estado_nuevo, motivo = calcular_transicion_estado(
            symbol=symbol,
            estado_previo=estado_previo,
            estado_calculado=estado_dashboard,
            precio_actual=precio_actual,
            entrada=entrada_g,
            stoploss=stoploss_g,
            tp=tp_g,
            zona_desde=zona_desde_g,
            zona_hasta=zona_hasta_g,
        )

        print(f"  FILTRADO_M15 TRACKING: {estado_previo} → {estado_nuevo} | {motivo}")

        if estado_nuevo != estado_previo:
            _update_estado_supabase_filtrado_m15(existing.get("id"), estado_nuevo, precio_actual)
        if symbol in _tracking_cache_filtrado_m15:
            _tracking_cache_filtrado_m15[symbol]["estado"] = estado_nuevo
            _tracking_cache_filtrado_m15[symbol]["precio_actual"] = precio_actual

        return _build_result_tracked(symbol, existing, fresh_result, estado_nuevo, motivo)

    # ── Fallback: estado no reconocido → usar fresco ──────────────────────────
    print(f"  FILTRADO_M15 TRACKING: Estado no reconocido ({estado_previo}) → fresco")
    return fresh_result


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

    Parte 3: gestión operativa completa:
      - Motor de Parte 2 para análisis fresco de mercado.
      - Modo seguimiento: ACTIVA → EN_ZONA → PROFIT → TP/SL.
      - PROFIT ↔ EN_ZONA si el precio vuelve a la zona antes de TP.
      - PAUSADA cuando nueva zona aparece con otra ACTIVA en seguimiento.
      - Historial independiente en Supabase (strategy_id = STRATEGY_ID).
      - TP ratio 1:2, filtro M15 obligatorio, micro zonas M1.

    Args:
        symbol: Symbol name (e.g. "Boom 1000 Index").
        df_m1: DataFrame con velas M1 (núcleo operativo).
        df_m15: DataFrame con velas M15 (filtro direccional obligatorio).

    Returns:
        dict con snapshot completo de la estrategia.
    """
    try:
        # 1. Análisis fresco del mercado (engine Parte 2)
        fresh_result = _engine.analyze(symbol=symbol, df_m1=df_m1, df_m15=df_m15)

        # 2. Aplicar modo seguimiento (Parte 3)
        result = _modo_seguimiento_filtrado_m15(
            symbol=symbol,
            fresh_result=fresh_result,
            df_m1=df_m1,
        )

        # 3. Sincronizar con Supabase solo si hay zona válida
        estado = result.get("estado", "")
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
        price = None
        if df_m1 is not None and not df_m1.empty:
            try:
                price = float(df_m1.iloc[-1]["close"])
            except Exception:
                price = None
        return create_sin_setup_micro_impulso_filtrado_m15_response(symbol=symbol, price=price)
