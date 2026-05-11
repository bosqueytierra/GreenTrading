#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SMC MICRO IMPULSO FILTRADO M15 strategy engine.

Arquitectura base — Parte 1.

Estrategia derivada de SMC MICRO IMPULSO con filtro direccional M15 obligatorio.
La lógica completa (filtro M15, micro BOS/CHOCH, barrida, OB, FVG, desplazamiento,
TP/SL, estados avanzados) se implementará en Parte 2.

Diferencias clave vs SMC_MICRO_IMPULSO:
  - M15: filtro direccional obligatorio (NO solo informativo).
  - M1: núcleo operativo (pendiente Parte 2).
  - H1: NO se usa.
  - strategy_id = "SMC_MICRO_IMPULSO_FILTRADO_M15" — completamente aislado.
"""

from datetime import datetime, timezone

STRATEGY_ID = "SMC_MICRO_IMPULSO_FILTRADO_M15"
STRATEGY_NAME = "SMC MICRO IMPULSO FILTRADO M15"
STRATEGY_KEY = "microimpulso_filtrado_m15"


# =============================================================================
# SIN SETUP RESPONSE
# =============================================================================

def create_sin_setup_micro_impulso_filtrado_m15_response(
    symbol: str,
    price: float = None,
    direccion_m15: str = "--",
    motivo: str = "ARQUITECTURA BASE - LÓGICA PENDIENTE",
) -> dict:
    """
    Crea respuesta mínima SIN SETUP para SMC_MICRO_IMPULSO_FILTRADO_M15.

    Por ahora todos los paths devuelven estado = "SIN SETUP" hasta que
    se implemente la lógica completa en Parte 2.

    Args:
        symbol: Symbol name.
        price: Current price (optional).
        direccion_m15: M15 directional filter result (informational for now).
        motivo: Reason for SIN SETUP.

    Returns:
        dict with base fields.
    """
    now = datetime.now(timezone.utc).isoformat()
    return {
        "symbol": symbol,
        "estrategia": STRATEGY_NAME,
        "strategy_key": STRATEGY_KEY,
        "price": price,
        "precio_actual": price,
        "direccion_indice": "--",
        "direccion_m15": direccion_m15,
        "cumple_m15": False,
        "micro_bos_choch": "--",
        "zona_desde": 0.0,
        "zona_hasta": 0.0,
        "zona_size": 0.0,
        "entrada": None,
        "stoploss": None,
        "tp": None,
        "sl": None,
        "score": 0,
        "ob": "NO",
        "fvg": "NO",
        "barrida": "NO",
        "desplazamiento": "--",
        "estado": "SIN SETUP",
        "motivo": motivo,
        "estado_dashboard": "SIN_SETUP",
        "estado_historial": "SIN_SETUP",
        "estado_final": "SIN_SETUP",
        # Métricas (preparadas en cero para Parte 2)
        "tp_puntos": 0.0,
        "sl_puntos": 0.0,
        "timestamp": now,
        "updated_at": now,
    }


# =============================================================================
# ENGINE STUB (Parte 2 implementará la lógica completa)
# =============================================================================

class SMCMicroImpulsoFiltradoM15Engine:
    """
    Motor base para SMC MICRO IMPULSO FILTRADO M15.

    Parte 1: solo retorna estructura base con estado SIN SETUP.
    Parte 2: implementará filtro M15, micro BOS/CHOCH, barrida, OB, FVG,
             desplazamiento, TP/SL y máquina de estados completa.
    """

    def analyze(
        self,
        symbol: str,
        df_m1=None,
        df_m15=None,
    ) -> dict:
        """
        Analiza un símbolo con la estrategia SMC MICRO IMPULSO FILTRADO M15.

        Parte 1: devuelve SIN SETUP con arquitectura base lista.

        Args:
            symbol: Symbol name.
            df_m1: DataFrame con velas M1 (núcleo operativo — Parte 2).
            df_m15: DataFrame con velas M15 (filtro direccional — Parte 2).

        Returns:
            dict con estructura base de la estrategia.
        """
        price = None
        if df_m1 is not None and not df_m1.empty:
            try:
                price = float(df_m1.iloc[-1]["close"])
            except Exception:
                price = None

        return create_sin_setup_micro_impulso_filtrado_m15_response(
            symbol=symbol,
            price=price,
        )
