#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GreenTrading Desktop - SMC MICRO IMPULSO FILTRADO M15 Service

Servicio de análisis para la estrategia SMC_MICRO_IMPULSO_FILTRADO_M15.
Completamente separado de los otros servicios SMC —
zero contaminación con SMC_M15_PRO, SMC_H1_M15_PRO y SMC_MICRO_IMPULSO.

Responsabilidades:
  - Orquestar el engine SMC_MICRO_IMPULSO_FILTRADO_M15
  - Cache de estado por símbolo (independiente de otras estrategias)
  - strategy_key = 'microimpulso_filtrado_m15'

Parte 1: arquitectura base. La lógica completa llega en Parte 2.
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

print("SMC_MICRO_IMPULSO_FILTRADO_M15_SERVICE_PATH:", __file__)

# Cache independiente — no comparte estado con ningún otro servicio
_setup_cache_micro_impulso_filtrado_m15: dict = {}

# Instancia del engine
_engine = SMCMicroImpulsoFiltradoM15Engine()


# =============================================================================
# SMART SYNC / DEBOUNCE (preparado para Parte 2)
# =============================================================================

def _has_relevant_changes(symbol: str, new_data: dict) -> bool:
    """
    Determina si hay cambios relevantes respecto al cache local.

    Por ahora siempre actualiza porque todos los resultados son SIN SETUP.
    En Parte 2 se activará la lógica de debounce real.

    Args:
        symbol: Symbol name.
        new_data: Nuevo dict con campos críticos.

    Returns:
        True si hay cambios relevantes, False en caso contrario.
    """
    if symbol not in _setup_cache_micro_impulso_filtrado_m15:
        _setup_cache_micro_impulso_filtrado_m15[symbol] = new_data
        return True

    old_data = _setup_cache_micro_impulso_filtrado_m15[symbol]

    critical_fields = ["estado", "entrada", "stoploss", "tp", "score", "zona_desde", "zona_hasta"]
    for field in critical_fields:
        if old_data.get(field) != new_data.get(field):
            print(
                f"MICRO_IMPULSO_FILTRADO_M15 SYNC TRIGGER: {symbol} - {field} "
                f"cambiado de {old_data.get(field)} a {new_data.get(field)}"
            )
            _setup_cache_micro_impulso_filtrado_m15[symbol] = new_data
            return True

    _setup_cache_micro_impulso_filtrado_m15[symbol] = new_data
    return False


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

    Parte 1: devuelve estructura base con estado SIN SETUP.
    Parte 2: implementará la lógica completa con filtro M15, micro BOS/CHOCH,
             barrida, OB, FVG, desplazamiento, TP/SL y estados avanzados.

    Args:
        symbol: Symbol name (e.g. "Boom 1000 Index").
        df_m1: DataFrame con velas M1 (núcleo operativo — Parte 2).
        df_m15: DataFrame con velas M15 (filtro direccional — Parte 2).

    Returns:
        dict con snapshot completo de la estrategia.
    """
    try:
        result = _engine.analyze(symbol=symbol, df_m1=df_m1, df_m15=df_m15)
        _has_relevant_changes(symbol, result)
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
