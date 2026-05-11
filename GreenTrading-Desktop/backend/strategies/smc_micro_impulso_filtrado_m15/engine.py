#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SMC MICRO IMPULSO FILTRADO M15 strategy engine.

Estrategia derivada de SMC MICRO IMPULSO con filtro direccional M15 obligatorio.

Diferencias clave vs SMC_MICRO_IMPULSO:
  - M15: filtro direccional OBLIGATORIO (bloquea si no alinea con índice).
  - M1: núcleo operativo completo — reutiliza íntegramente crear_zona_micro_impulso
        (micro BOS/CHOCH, barrida, OB+FVG unión, zona, score idénticos).
  - H1: NO se usa.
  - TP ratio 1:2 (en lugar de 1:1 de MICRO IMPULSO normal).
  - strategy_id = "SMC_MICRO_IMPULSO_FILTRADO_M15" — completamente aislado.

Estados:
  - NO CUMPLE DIRECCIÓN M15 (filtro M15 no alinea)
  - SIN SETUP                (sin zona micro válida)
  - ACTIVA                   (zona válida encontrada)
  - EN_ZONA, PROFIT, TP, SL, PAUSADA, DESCARTADA (máquina de estados en service)
"""

import traceback
from datetime import datetime, timezone

import pandas as pd

# Helpers de smc_m15_pro usados para el filtro direccional M15.
from strategies.smc_m15_pro.engine import (
    direccion_operativa_por_indice,
    detectar_swings,
    detectar_estructura,
    detectar_fvg,
)

# Lógica de zona delegada íntegramente al engine de MICRO IMPULSO normal,
# garantizando zonas idénticas (OB+FVG unión, mismos parámetros M1).
from strategies.smc_micro_impulso.engine import (
    detectar_swings_m1,
    crear_zona_micro_impulso,
)

STRATEGY_ID = "SMC_MICRO_IMPULSO_FILTRADO_M15"
STRATEGY_NAME = "SMC MICRO IMPULSO FILTRADO M15"
STRATEGY_KEY = "microimpulso_filtrado_m15"

# Configuración M15 (filtro direccional)
SWING_LOOKBACK_M15 = 3

# TP 1:2 (única diferencia operativa vs MICRO IMPULSO normal que usa 1:1)
TP_RATIO = 2.0


# =============================================================================
# SIN SETUP / NO CUMPLE RESPONSE HELPERS
# =============================================================================

def create_sin_setup_micro_impulso_filtrado_m15_response(
    symbol: str,
    price: float = None,
    direccion_indice: str = "--",
    direccion_m15: str = "--",
    cumple_m15: bool = False,
    motivo: str = "SIN SETUP",
    estado: str = "SIN SETUP",
) -> dict:
    """
    Crea respuesta para estados SIN SETUP y NO CUMPLE DIRECCIÓN M15.

    Args:
        symbol: Nombre del símbolo.
        price: Precio actual (opcional).
        direccion_indice: Dirección operativa del índice (ALCISTA/BAJISTA/--).
        direccion_m15: Dirección estructural M15 (ALCISTA/BAJISTA/--).
        cumple_m15: True si la dirección M15 alinea con el índice.
        motivo: Razón del estado.
        estado: "SIN SETUP" o "NO CUMPLE DIRECCIÓN M15".

    Returns:
        dict con snapshot completo con campos en cero/vacíos.
    """
    now = datetime.now(timezone.utc).isoformat()
    return {
        "symbol": symbol,
        "estrategia": STRATEGY_NAME,
        "strategy_key": STRATEGY_KEY,
        "price": price,
        "precio_actual": price,
        "direccion_indice": direccion_indice,
        "direccion_m15": direccion_m15,
        "cumple_m15": cumple_m15,
        "micro_bos_choch": "--",
        "zona_desde": 0.0,
        "zona_hasta": 0.0,
        "zona_size": 0.0,
        "entrada": None,
        "stoploss": None,
        # tp_1_1 mantiene compatibilidad con el schema de Supabase (columna compartida).
        # Para esta estrategia, tp_1_1 almacena el TP operativo 1:2 (no 1:1).
        # Usar tp_operativo o tp para lógica interna; tp_ratio indica el ratio real.
        "tp": None,
        "tp_1_1": None,     # TP operativo 1:2 — nombre heredado de schema Supabase
        "tp_operativo": None,  # Alias explícito: mismo valor que tp_1_1
        "tp_ratio": TP_RATIO,  # Ratio real: 2 (no 1)
        "sl": None,
        "score": 0,
        "ob": "NO",
        "fvg": "NO",
        "barrida": "NO",
        "desplazamiento": "NO",
        "estado": estado,
        "motivo": motivo,
        "estado_dashboard": "SIN_SETUP",
        "estado_historial": "SIN_SETUP",
        "estado_final": "SIN_SETUP",
        "tp_puntos": 0.0,
        "sl_puntos": 0.0,
        "timestamp": now,
        "updated_at": now,
    }


# =============================================================================
# PURE INTERNAL HELPERS — ISOLATED, NO SHARED STATE
# =============================================================================

def _calcular_direccion_m15(df_m15: pd.DataFrame) -> str:
    """
    Calcula la dirección estructural del timeframe M15.

    Usa detectar_swings + detectar_estructura del engine M15 PRO (funciones puras).
    Devuelve "ALCISTA", "BAJISTA" o "--" si no hay datos suficientes.

    Args:
        df_m15: DataFrame de velas M15.

    Returns:
        "ALCISTA", "BAJISTA" o "--".
    """
    if df_m15 is None or len(df_m15) < (SWING_LOOKBACK_M15 * 2 + 1):
        return "--"
    try:
        swings_m15 = detectar_swings(df_m15, lookback=SWING_LOOKBACK_M15)
        _, tendencia_m15 = detectar_estructura(df_m15, swings_m15)
        if tendencia_m15 is None:
            return "--"
        return tendencia_m15.upper()
    except Exception as exc:
        print(f"  FILTRADO_M15: error calculando direccion M15 -- {exc}")
        return "--"


def _calcular_tp_sl_1_2(
    zona_desde: float,
    zona_hasta: float,
    direccion: str,
) -> tuple:
    """
    Calcula SL y TP con ratio 1:2 para SMC_MICRO_IMPULSO_FILTRADO_M15.

    ALCISTA (Boom):
        sl = zona_desde
        tp = zona_hasta + (zona_size * TP_RATIO)   # TP_RATIO=2 → ratio 1:2

    BAJISTA (Crash):
        sl = zona_hasta
        tp = zona_desde - (zona_size * TP_RATIO)   # TP_RATIO=2 → ratio 1:2

    Args:
        zona_desde: Límite inferior de la zona (low del OB).
        zona_hasta: Límite superior de la zona (high del OB).
        direccion: "ALCISTA" o "BAJISTA".

    Returns:
        Tuple (sl, tp) redondeados a 2 decimales.
    """
    zona_size = abs(zona_hasta - zona_desde)
    if direccion == "ALCISTA":
        sl = zona_desde
        tp = zona_hasta + zona_size * TP_RATIO
    else:
        sl = zona_hasta
        tp = zona_desde - zona_size * TP_RATIO
    return round(sl, 2), round(tp, 2)


def _calcular_entrada(zona_desde: float, zona_hasta: float, direccion: str) -> float:
    """
    Calcula el nivel de entrada desde la zona OB.

    ALCISTA: entrada = zona_hasta (precio entra al OB desde arriba).
    BAJISTA: entrada = zona_desde (precio entra al OB desde abajo).
    """
    if direccion == "ALCISTA":
        return round(zona_hasta, 2)
    return round(zona_desde, 2)


# =============================================================================
# CORE ANALYSIS FUNCTION
# =============================================================================

def analyze_symbol_filtrado_m15(
    symbol: str,
    df_m1: pd.DataFrame,
    df_m15: pd.DataFrame,
) -> dict:
    """
    Analiza un símbolo con la estrategia SMC MICRO IMPULSO FILTRADO M15.

    Flujo:
    1. Verificar datos mínimos → SIN SETUP si faltan.
    2. Obtener precio actual desde M1.
    3. Detectar dirección del índice (Boom=ALCISTA, Crash=BAJISTA).
    4. Calcular dirección estructural M15.
    5. Validar filtro M15 obligatorio: si no alinea → NO CUMPLE DIRECCIÓN M15.
    6. Detectar estructura M1 (micro BOS/CHOCH, FVGs) — igual que MICRO IMPULSO normal.
    7. Construir zona vía crear_zona_micro_impulso — MISMA lógica que MICRO IMPULSO normal
       (OB+FVG unión, mismos parámetros M1, mismo score).
    8. Calcular TP/SL con ratio 1:2 (única diferencia operativa vs MICRO IMPULSO 1:1).
    9. Retornar payload completo.

    Garantía: para cualquier símbolo donde M15 cumple, zona_desde / zona_hasta /
    micro_bos_choch / ob / fvg / barrida / desplazamiento / score son IDÉNTICOS
    a los que retorna /api/smc/micro-impulso/snapshot.
    entrada / stoploss se derivan de la misma zona pero con ratio TP 1:2 (vs 1:1).

    Args:
        symbol: Nombre del símbolo.
        df_m1: DataFrame de velas M1 (núcleo operativo).
        df_m15: DataFrame de velas M15 (filtro direccional obligatorio).

    Returns:
        dict con snapshot completo de la estrategia.
    """
    print(f"\n{'='*60}")
    print(f"SMC_MICRO_IMPULSO_FILTRADO_M15 Analyzing {symbol}")
    print(f"{'='*60}")

    now = datetime.now(timezone.utc).isoformat()

    # ------------------------------------------------------------------
    # GUARD: datos mínimos M1
    # ------------------------------------------------------------------
    if df_m1 is None or len(df_m1) == 0:
        print(f"  ERROR: No hay datos M1 para {symbol}")
        return create_sin_setup_micro_impulso_filtrado_m15_response(
            symbol=symbol,
            motivo="SIN DATOS M1",
        )

    # Precio actual
    try:
        precio_actual = float(df_m1.iloc[-1]["close"])
    except Exception:
        precio_actual = None

    print(f"  OK: M1={len(df_m1)}" + (f" M15={len(df_m15)}" if df_m15 is not None else " M15=N/A"))
    print(f"  precio_actual: {precio_actual}")

    def _sin_setup(motivo, direccion_indice="--", direccion_m15="--", cumple_m15=False, estado="SIN SETUP"):
        return create_sin_setup_micro_impulso_filtrado_m15_response(
            symbol=symbol,
            price=precio_actual,
            direccion_indice=direccion_indice,
            direccion_m15=direccion_m15,
            cumple_m15=cumple_m15,
            motivo=motivo,
            estado=estado,
        )

    # ------------------------------------------------------------------
    # PASO 1: Dirección operativa del índice (Boom / Crash)
    # ------------------------------------------------------------------
    direccion_indice = direccion_operativa_por_indice(symbol)
    if not direccion_indice:
        print(f"  SIN_SETUP: {symbol} no es Boom ni Crash")
        return _sin_setup("SIMBOLO NO CLASIFICADO")

    print(f"  direccion_indice: {direccion_indice}")

    # ------------------------------------------------------------------
    # PASO 2: Dirección estructural M15
    # ------------------------------------------------------------------
    if df_m15 is None or len(df_m15) == 0:
        print(f"  SIN_SETUP: sin datos M15 para filtro direccional")
        return _sin_setup("SIN DATOS M15", direccion_indice=direccion_indice)

    direccion_m15 = _calcular_direccion_m15(df_m15)
    print(f"  direccion_m15: {direccion_m15}")

    # ------------------------------------------------------------------
    # PASO 3: Filtro M15 — obligatorio
    # ------------------------------------------------------------------
    cumple_m15 = (direccion_m15 != "--") and (direccion_m15 == direccion_indice)
    if not cumple_m15:
        motivo_no_cumple = (
            f"M15={direccion_m15} != INDICE={direccion_indice}"
            if direccion_m15 != "--"
            else "DIRECCION M15 INDETERMINADA"
        )
        print(f"  NO CUMPLE DIRECCION M15: {motivo_no_cumple}")
        return _sin_setup(
            motivo=motivo_no_cumple,
            direccion_indice=direccion_indice,
            direccion_m15=direccion_m15,
            cumple_m15=False,
            estado="NO CUMPLE DIRECCIÓN M15",
        )

    print(f"  CUMPLE M15: {direccion_m15} == {direccion_indice}")

    # ------------------------------------------------------------------
    # PASO 4: Estructura M1 — micro BOS/CHOCH
    # Misma lógica que MICRO IMPULSO normal (lookback=2, mismos parámetros).
    # ------------------------------------------------------------------
    try:
        swings_m1 = detectar_swings_m1(df_m1)
        eventos_m1, _ = detectar_estructura(df_m1, swings_m1)
        fvgs_m1 = detectar_fvg(df_m1)
    except Exception as exc:
        print(f"  ERROR estructura M1: {exc}")
        traceback.print_exc()
        return _sin_setup(
            "ERROR ESTRUCTURA M1",
            direccion_indice=direccion_indice,
            direccion_m15=direccion_m15,
            cumple_m15=True,
        )

    print(f"  swings_m1: {len(swings_m1)}, eventos_m1: {len(eventos_m1)}, fvgs_m1: {len(fvgs_m1)}")

    # ------------------------------------------------------------------
    # PASO 5–9: Zona micro — MISMA lógica que MICRO IMPULSO normal.
    # Se delega íntegramente en crear_zona_micro_impulso para garantizar
    # que zona_desde/zona_hasta/OB/FVG/score son idénticos al snapshot
    # de /api/smc/micro-impulso/snapshot para este símbolo.
    # ------------------------------------------------------------------
    zona = crear_zona_micro_impulso(df_m1, eventos_m1, fvgs_m1, symbol, precio_actual)

    if not zona:
        print(f"  SIN_SETUP: ningun candidato produjo zona micro valida")
        return _sin_setup(
            "SIN ZONA MICRO VALIDA EN M1",
            direccion_indice=direccion_indice,
            direccion_m15=direccion_m15,
            cumple_m15=True,
        )

    # ------------------------------------------------------------------
    # PASO 10: Extraer zona — mismos valores que MICRO IMPULSO normal.
    # ------------------------------------------------------------------
    zona_desde = float(zona["zona_desde"])
    zona_hasta = float(zona["zona_hasta"])
    zona_size = abs(zona_hasta - zona_desde)
    direccion = zona.get("direccion_operativa", zona.get("direccion", direccion_indice))
    micro_bos_choch = zona["evento"]["evento"]
    score = zona.get("score", 0)
    has_ob = zona.get("ob") is not None
    has_fvg = zona.get("fvg") is not None
    has_barrida = zona.get("barrida") is not None
    has_desp = bool(zona.get("desplazamiento", {}).get("valido", False))

    # ------------------------------------------------------------------
    # PASO 11: TP/SL y entrada.
    # Misma zona que MICRO IMPULSO normal; solo cambia el ratio TP: 1:2.
    # ------------------------------------------------------------------
    sl, tp = _calcular_tp_sl_1_2(zona_desde, zona_hasta, direccion)
    entrada = _calcular_entrada(zona_desde, zona_hasta, direccion)

    tp_puntos = abs(tp - entrada)
    sl_puntos = abs(sl - entrada)

    print(f"\n  ACTIVA:")
    print(f"    micro_bos_choch: {micro_bos_choch}")
    print(f"    zona: [{zona_desde}, {zona_hasta}] size={round(zona_size, 4)}")
    print(f"    entrada: {entrada}, sl: {sl}, tp: {tp} (ratio 1:{TP_RATIO})")
    print(f"    ob: {'SI' if has_ob else 'NO'}, fvg: {'SI' if has_fvg else 'NO'}")
    print(f"    barrida: {'SI' if has_barrida else 'NO'}, desp: {'SI' if has_desp else 'NO'}")
    print(f"    score: {score}")

    return {
        "symbol": symbol,
        "estrategia": STRATEGY_NAME,
        "strategy_key": STRATEGY_KEY,
        "price": precio_actual,
        "precio_actual": precio_actual,
        "direccion_indice": direccion_indice,
        "direccion_m15": direccion_m15,
        "cumple_m15": True,
        "micro_bos_choch": micro_bos_choch,
        "zona_desde": round(zona_desde, 2),
        "zona_hasta": round(zona_hasta, 2),
        "zona_size": round(zona_size, 4),
        "entrada": entrada,
        "stoploss": sl,
        # tp_1_1 mantiene compatibilidad con el schema de Supabase (columna compartida).
        # Para esta estrategia, tp_1_1 almacena el TP operativo 1:2 (no 1:1).
        # Usar tp_operativo o tp para lógica interna; tp_ratio indica el ratio real.
        "tp": tp,
        "tp_1_1": tp,           # TP operativo 1:2 — nombre heredado de schema Supabase
        "tp_operativo": tp,     # Alias explícito: mismo valor que tp_1_1
        "tp_ratio": TP_RATIO,   # Ratio real: 2 (no 1)
        "sl": sl,
        "ob": "SI" if has_ob else "NO",
        "fvg": "SI" if has_fvg else "NO",
        "barrida": "SI" if has_barrida else "NO",
        "desplazamiento": "SI" if has_desp else "NO",
        "estado": "ACTIVA",
        "motivo": f"M15={direccion_m15} | {micro_bos_choch} | OB={'SI' if has_ob else 'NO'} | FVG={'SI' if has_fvg else 'NO'} | score={score}",
        "estado_dashboard": "ACTIVA",
        "estado_historial": "ACTIVA",
        "estado_final": "ACTIVA",
        "tp_puntos": round(tp_puntos, 4),
        "sl_puntos": round(sl_puntos, 4),
        "timestamp": now,
        "updated_at": now,
    }


# =============================================================================
# ENGINE CLASS (wraps the pure analysis function)
# =============================================================================

class SMCMicroImpulsoFiltradoM15Engine:
    """
    Motor para SMC MICRO IMPULSO FILTRADO M15.

    Reutiliza íntegramente la lógica de zona de SMC MICRO IMPULSO normal y
    aplica como único filtro adicional la dirección estructural M15 obligatoria.

    Diferencias vs SMC MICRO IMPULSO normal:
      - Filtro M15 obligatorio (bloquea si M15 no alinea con el índice).
      - TP ratio 1:2 (en lugar de 1:1).
      - strategy_id / strategy_key propios — historial completamente aislado.
    """

    def analyze(
        self,
        symbol: str,
        df_m1=None,
        df_m15=None,
    ) -> dict:
        """
        Analiza un símbolo con la estrategia SMC MICRO IMPULSO FILTRADO M15.

        Args:
            symbol: Nombre del símbolo.
            df_m1: DataFrame con velas M1 (núcleo operativo).
            df_m15: DataFrame con velas M15 (filtro direccional obligatorio).

        Returns:
            dict con snapshot completo de la estrategia.
        """
        try:
            return analyze_symbol_filtrado_m15(
                symbol=symbol,
                df_m1=df_m1,
                df_m15=df_m15,
            )
        except Exception as exc:
            print(f"FILTRADO_M15 ENGINE ERROR: {symbol} -- {exc}")
            traceback.print_exc()
            price = None
            if df_m1 is not None and not df_m1.empty:
                try:
                    price = float(df_m1.iloc[-1]["close"])
                except Exception:
                    pass
            return create_sin_setup_micro_impulso_filtrado_m15_response(
                symbol=symbol,
                price=price,
                motivo="ERROR INTERNO ENGINE",
            )
