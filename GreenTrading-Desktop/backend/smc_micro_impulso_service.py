#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GreenTrading Desktop - SMC MICRO IMPULSO Service

Servicio de análisis para la estrategia SMC_MICRO_IMPULSO.
Completamente separado de smc_m15_service.py y smc_h1m15_service.py —
zero contaminación.

Responsabilidades:
  - Orquestar el engine SMC_MICRO_IMPULSO
  - Smart sync / debounce hacia Supabase con strategy_id = 'SMC_MICRO_IMPULSO'
  - Cache de estado por símbolo (separada de las otras estrategias)
"""

import traceback
from datetime import datetime, timezone

import pandas as pd

from strategies.smc_micro_impulso.engine import (
    SMCMicroImpulsoEngine,
    create_sin_setup_micro_impulso_response,
    STRATEGY_ID,
    STRATEGY_NAME,
)

print("SMC_MICRO_IMPULSO_SERVICE_PATH:", __file__)

try:
    import supabase_service
except ImportError:
    print("WARNING: Supabase service not available")
    supabase_service = None

# Valores considerados como "SI/verdadero" en campos ob/fvg/barrida
TRUTHY_VALUES = {"SÍ", "SI", "YES"}

# Cache independiente — no comparte estado con _setup_cache (M15 PRO) ni _setup_cache_h1m15
_setup_cache_micro_impulso: dict = {}


# =============================================================================
# SMART SYNC / DEBOUNCE
# =============================================================================

def _has_relevant_changes_micro_impulso(symbol: str, new_data: dict) -> bool:
    """
    Determina si hay cambios relevantes para sincronizar con Supabase.

    Solo actualiza cuando cambian campos críticos:
      - estado, entrada, stoploss, tp_1_1, score, zona_desde/zona_hasta
      - precio (cambio significativo >1%)

    Args:
        symbol: Symbol name.
        new_data: Nuevo dict con campos críticos.

    Returns:
        True si hay cambios relevantes, False en caso contrario.
    """
    if symbol not in _setup_cache_micro_impulso:
        _setup_cache_micro_impulso[symbol] = new_data
        return True

    old_data = _setup_cache_micro_impulso[symbol]

    critical_fields = ["estado", "entrada", "stoploss", "tp_1_1", "score", "zona_desde", "zona_hasta"]
    for field in critical_fields:
        if old_data.get(field) != new_data.get(field):
            print(
                f"MICRO_IMPULSO SYNC TRIGGER: {symbol} - {field} "
                f"cambiado de {old_data.get(field)} a {new_data.get(field)}"
            )
            _setup_cache_micro_impulso[symbol] = new_data
            return True

    old_price = old_data.get("precio_actual", 0)
    new_price = new_data.get("precio_actual", 0)
    if old_price and old_price > 0:
        price_change_pct = abs(new_price - old_price) / old_price * 100
        if price_change_pct > 1.0:
            print(f"MICRO_IMPULSO SYNC TRIGGER: {symbol} - precio cambió {price_change_pct:.2f}%")
            _setup_cache_micro_impulso[symbol] = new_data
            return True

    return False


def sync_setup_to_supabase_micro_impulso(analysis_result: dict) -> None:
    """
    Sincroniza setup SMC_MICRO_IMPULSO con Supabase solo si hay cambios relevantes.

    Implementa:
      - Smart sync / debounce (evita spam updates)
      - Duplicate closed zone guard (aislado por strategy_id='SMC_MICRO_IMPULSO')
      - NO toca registros de SMC_M15_PRO ni SMC_H1_M15_PRO

    Args:
        analysis_result: Dict con resultado del engine SMC_MICRO_IMPULSO.
    """
    if not supabase_service:
        print("  MICRO_IMPULSO SUPABASE SYNC: Service not available")
        return

    estado_actual = analysis_result.get("estado", "")
    if estado_actual in ("SIN SETUP", "SIN_SETUP"):
        print(f"  MICRO_IMPULSO SUPABASE SYNC: Skipping {analysis_result.get('symbol')} - SIN_SETUP")
        return

    if not analysis_result.get("entrada") or not analysis_result.get("stoploss"):
        print(
            f"  MICRO_IMPULSO SUPABASE SYNC: Skipping {analysis_result.get('symbol')} "
            f"- falta entrada o stoploss"
        )
        return

    symbol = analysis_result["symbol"]

    critical_data = {
        "estado": analysis_result.get(
            "estado_historial", analysis_result.get("estado_dashboard", "ESPERANDO_ENTRADA")
        ),
        "entrada": analysis_result.get("entrada"),
        "stoploss": analysis_result.get("stoploss"),
        "tp_1_1": analysis_result.get("tp_1_1"),
        "score": analysis_result.get("score", 0),
        "zona_desde": analysis_result.get("zona_madre_m1", {}).get("desde", 0),
        "zona_hasta": analysis_result.get("zona_madre_m1", {}).get("hasta", 0),
        "precio_actual": analysis_result.get("price"),
    }

    if not _has_relevant_changes_micro_impulso(symbol, critical_data):
        print(f"  MICRO_IMPULSO SUPABASE SYNC: Skipping {symbol} - no hay cambios relevantes")
        return

    print(f"  MICRO_IMPULSO SUPABASE SYNC: Preparando sync para {symbol}")

    setup_data = {
        "strategy_id": STRATEGY_ID,
        "strategy_name": STRATEGY_NAME,
        "symbol": symbol,
        "tendencia_h1": "--",
        "tendencia_m15": analysis_result.get("tendencia_m15", "--"),
        "ultimo_evento_m15": analysis_result.get("ultimo_evento_m1", "--"),
        "entrada": critical_data["entrada"],
        "stoploss": critical_data["stoploss"],
        "tp_1_1": critical_data["tp_1_1"],
        "score": critical_data["score"],
        "ob": analysis_result.get("ob") in TRUTHY_VALUES,
        "fvg": analysis_result.get("fvg") in TRUTHY_VALUES,
        "barrida": analysis_result.get("barrida") in TRUTHY_VALUES,
        "estado": critical_data["estado"],
        "estado_dashboard": analysis_result.get("estado_dashboard", "ESPERANDO_ENTRADA"),
        "precio_detectado": critical_data["precio_actual"],
        "precio_actual": critical_data["precio_actual"],
    }

    existing = None
    if hasattr(supabase_service, "get_active_setup"):
        existing = supabase_service.get_active_setup(
            STRATEGY_ID, symbol, setup_data["entrada"], setup_data["stoploss"]
        )

    if existing:
        setup_id = existing["id"]
        updates = {
            "estado": setup_data["estado"],
            "estado_dashboard": setup_data["estado_dashboard"],
            "precio_actual": setup_data["precio_actual"],
        }
        print(
            f"  MICRO_IMPULSO SUPABASE SYNC: UPDATE id={setup_id}, "
            f"estado={setup_data['estado']}"
        )
        result = supabase_service.update_setup(setup_id, updates)
        if result:
            print(f"MICRO_IMPULSO SUPABASE SYNC: Updated {symbol}")
        else:
            print(f"MICRO_IMPULSO SUPABASE SYNC WARNING: update devolvió None para {symbol}")
    else:
        # Duplicate closed zone guard (aislado por strategy_id)
        closed_setup = None
        if (
            hasattr(supabase_service, "get_closed_setup_by_levels")
            and setup_data.get("tp_1_1") is not None
        ):
            closed_setup = supabase_service.get_closed_setup_by_levels(
                STRATEGY_ID,
                symbol,
                setup_data["entrada"],
                setup_data["stoploss"],
                setup_data["tp_1_1"],
            )

        decision = "SKIP_ALREADY_CLOSED" if closed_setup else "CREATE_NEW"
        print(f"\nDUPLICATE_CLOSED_ZONE_CHECK (MICRO_IMPULSO):")
        print(f"  symbol: {symbol}")
        print(f"  strategy_id: {STRATEGY_ID}")
        print(f"  entrada: {setup_data['entrada']}")
        print(f"  stoploss: {setup_data['stoploss']}")
        print(f"  tp_1_1: {setup_data['tp_1_1']}")
        print(f"  found_closed_setup: {bool(closed_setup)}")
        print(f"  closed_estado: {closed_setup.get('estado') if closed_setup else None}")
        print(f"  closed_id: {closed_setup.get('id') if closed_setup else None}")
        print(f"  decision: {decision}")

        if closed_setup:
            # Zona ya cerrada — resetear display a SIN_SETUP
            analysis_result["zona_madre_m1"] = {"desde": 0, "hasta": 0}
            analysis_result["entrada"] = None
            analysis_result["stoploss"] = None
            analysis_result["tp_1_1"] = None
            analysis_result["score"] = 0
            analysis_result["ob"] = "NO"
            analysis_result["fvg"] = "NO"
            analysis_result["barrida"] = "NO"
            analysis_result["desplazamiento_valido"] = "NO"
            analysis_result["estado_dashboard"] = "SIN_SETUP"
            analysis_result["estado_historial"] = "SIN_SETUP"
            analysis_result["estado_final"] = "SIN_SETUP"
            analysis_result["estado"] = "SIN SETUP"
            _setup_cache_micro_impulso[symbol] = {
                "estado": "SIN_SETUP",
                "entrada": None,
                "stoploss": None,
                "tp_1_1": None,
                "score": 0,
                "zona_desde": 0,
                "zona_hasta": 0,
                "precio_actual": analysis_result.get("price"),
            }
            print(
                f"  MICRO_IMPULSO SUPABASE SYNC: SKIP create_setup — "
                f"zona ya cerrada (TP/SL)"
            )
            return

        result = supabase_service.create_setup(setup_data)
        if result:
            print(f"MICRO_IMPULSO SUPABASE SYNC: Created setup for {symbol}, id={result.get('id')}")
        else:
            print(f"MICRO_IMPULSO SUPABASE SYNC WARNING: create_setup devolvió None para {symbol}")


# =============================================================================
# MAIN ANALYSIS FUNCTION (PUBLIC FACADE)
# =============================================================================

def analyze_symbol_smc_micro_impulso(
    symbol: str,
    df_m1: pd.DataFrame,
    df_m15: pd.DataFrame = None,
) -> dict:
    """
    Fachada pública para análisis SMC_MICRO_IMPULSO.

    Flujo:
    1. Delegar al engine SMCMicroImpulsoEngine.
    2. Si hay zona válida: sincronizar con Supabase (strategy_id='SMC_MICRO_IMPULSO').
    3. Retornar payload sin modificar.

    Args:
        symbol: Symbol name.
        df_m1: M1 candles DataFrame (núcleo operativo).
        df_m15: M15 candles DataFrame (opcional, solo informativo).

    Returns:
        dict con resultado SMC_MICRO_IMPULSO.
    """
    engine = SMCMicroImpulsoEngine()

    result = engine.analyze(
        symbol=symbol,
        df_h1=None,
        df_m15=df_m15,
        df_m1=df_m1,
        supabase_service=supabase_service,
        create_sin_setup_response=create_sin_setup_micro_impulso_response,
    )

    if (
        result.get("estado") not in ("SIN SETUP", "SIN_SETUP")
        and result.get("entrada") is not None
        and result.get("stoploss") is not None
    ):
        sync_setup_to_supabase_micro_impulso(result)

    return result
