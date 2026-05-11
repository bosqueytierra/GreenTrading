#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SMC MICRO IMPULSO FILTRADO M15 strategy engine.

Parte 2: implementación completa del motor lógico.

Estrategia derivada de SMC MICRO IMPULSO con filtro direccional M15 obligatorio.

Diferencias clave vs SMC_MICRO_IMPULSO:
  - M15: filtro direccional OBLIGATORIO (bloquea si no alinea con índice).
  - M1: núcleo operativo completo (micro BOS/CHOCH, barrida, OB, FVG, zona).
  - H1: NO se usa.
  - Zona: SIEMPRE desde micro OB M1 (no zona madre M15, no OB+FVG unión).
  - TP ratio 1:2 (sl=zona_desde / tp=zona_hasta+(size*2) para ALCISTA).
  - strategy_id = "SMC_MICRO_IMPULSO_FILTRADO_M15" — completamente aislado.

Estados implementados (Parte 2):
  - NO CUMPLE DIRECCIÓN M15
  - SIN SETUP
  - ACTIVA

Estados pendientes (Parte 3):
  - EN_ZONA, PROFIT, TP, SL, PAUSADA, DESCARTADA.
"""

import traceback
from datetime import datetime, timezone

import pandas as pd

# Pure helpers reutilizados de smc_m15_pro (funciones sin estado ni efectos secundarios).
from strategies.smc_m15_pro.engine import (
    direccion_operativa_por_indice,
    validar_zona_operativa,
    detectar_swings,
    detectar_estructura,
    detectar_fvg,
    buscar_order_block,
    detectar_barrida_previa,
)

STRATEGY_ID = "SMC_MICRO_IMPULSO_FILTRADO_M15"
STRATEGY_NAME = "SMC MICRO IMPULSO FILTRADO M15"
STRATEGY_KEY = "microimpulso_filtrado_m15"

# Configuración M15 (filtro direccional)
SWING_LOOKBACK_M15 = 3

# Configuración M1 (núcleo operativo)
SWING_LOOKBACK_M1 = 2          # micro swings con ventana reducida
BARRIDA_LOOKBACK_M1 = 20       # velas hacia atrás para buscar barrida local
DESPLAZAMIENTO_VENTANA = 5     # velas después del evento para validar impulso
DESPLAZAMIENTO_MIN_VELAS = 1   # min velas en dirección correcta (estrategia agresiva)

# TP 1:2
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


def _detectar_desplazamiento_m1(
    df_m1: pd.DataFrame,
    evento: dict,
    ventana: int = DESPLAZAMIENTO_VENTANA,
    min_velas: int = DESPLAZAMIENTO_MIN_VELAS,
) -> dict:
    """
    Valida desplazamiento impulsivo fuerte después del evento estructural M1.

    Lógica OR agresiva: válido si rango > 0 Y (velas_favor >= min_velas O movimiento neto correcto).

    Args:
        df_m1: DataFrame de velas M1.
        evento: Evento estructural M1 con campos 'index' y 'evento'.
        ventana: Número de velas a analizar después del evento.
        min_velas: Mínimo de velas en dirección correcta para validar.

    Returns:
        dict con valido (bool), velas_favor (int), rango (float).
    """
    idx = evento.get("index", -1)
    direccion = "ALCISTA" if "ALCISTA" in evento.get("evento", "") else "BAJISTA"

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

    close_evento = float(df_m1.iloc[idx]["close"]) if idx < len(df_m1) else None
    close_final = float(tramo.iloc[-1]["close"]) if len(tramo) > 0 else None
    net_ok = False
    if close_evento is not None and close_final is not None:
        if direccion == "ALCISTA":
            net_ok = close_final > close_evento
        else:
            net_ok = close_final < close_evento

    valido = rango > 0 and (velas_favor >= min_velas or net_ok)

    print(f"\nDESPLAZAMIENTO_FILTRADO_M15:")
    print(f"  evento_index: {idx}, direccion: {direccion}")
    print(f"  velas_analizadas: {len(tramo)}, velas_favor: {velas_favor}, min_velas: {min_velas}")
    print(f"  rango: {round(rango, 4)}, net_ok: {net_ok}, valido: {valido}")

    return {"valido": valido, "velas_favor": velas_favor, "rango": rango}


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
    5. Validar filtro M15: si no alinea → NO CUMPLE DIRECCIÓN M15.
    6. Detectar estructura M1 (micro BOS/CHOCH).
    7. Filtrar eventos M1 alineados con dirección del índice.
    8. Para cada candidato (último → primero):
       a. Desplazamiento impulsivo.
       b. Micro OB M1.
       c. Si no hay OB → siguiente candidato.
       d. Micro FVG M1 (confirmación adicional).
       e. Barrida local M1.
       f. Construir zona desde OB.
       g. Validar zona operativa (lado correcto del precio).
    9. Calcular score (0–6).
    10. Verificar condiciones mínimas ACTIVA.
    11. Calcular TP/SL 1:2 y entrada.
    12. Retornar payload completo.

    Args:
        symbol: Nombre del símbolo.
        df_m1: DataFrame de velas M1 (núcleo operativo).
        df_m15: DataFrame de velas M15 (filtro direccional).

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
    # ------------------------------------------------------------------
    try:
        swings_m1 = detectar_swings(df_m1, lookback=SWING_LOOKBACK_M1)
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

    # Filtrar eventos alineados con la dirección del índice
    eventos_alineados = [
        ev for ev in eventos_m1
        if ("ALCISTA" in ev["evento"] and direccion_indice == "ALCISTA")
        or ("BAJISTA" in ev["evento"] and direccion_indice == "BAJISTA")
    ]

    if not eventos_alineados:
        print(f"  SIN_SETUP: no hay micro BOS/CHOCH alineados con {direccion_indice}")
        return _sin_setup(
            f"SIN MICRO BOS/CHOCH {direccion_indice} EN M1",
            direccion_indice=direccion_indice,
            direccion_m15=direccion_m15,
            cumple_m15=True,
        )

    # ------------------------------------------------------------------
    # PASO 5–9: Buscar zona micro desde el último evento hacia atrás
    # ------------------------------------------------------------------
    zona_encontrada = None

    for evento in reversed(eventos_alineados):
        ev_nombre = evento["evento"]
        ev_idx = evento["index"]
        direccion_ev = "ALCISTA" if "ALCISTA" in ev_nombre else "BAJISTA"

        print(f"\n  CANDIDATO: {ev_nombre} idx={ev_idx}")

        # PASO 5: desplazamiento impulsivo
        desp = _detectar_desplazamiento_m1(df_m1, evento)
        if not desp["valido"]:
            print(f"    SKIP: desplazamiento invalido")
            continue

        # PASO 6: micro OB M1 — obligatorio para construir zona
        ob = buscar_order_block(df_m1, evento)
        if not ob:
            print(f"    SKIP: sin micro OB M1")
            continue

        print(f"    OB: {ob['tipo']} desde={ob['desde']} hasta={ob['hasta']}")

        # PASO 7: micro FVG M1 (confirmacion adicional -- no bloquea)
        fvg_tipo_esperado = "FVG_ALCISTA" if direccion_ev == "ALCISTA" else "FVG_BAJISTA"
        fvgs_validos = [
            f for f in fvgs_m1
            if f["index"] <= ev_idx and f["tipo"] == fvg_tipo_esperado
        ]
        fvg = fvgs_validos[-1] if fvgs_validos else None
        if fvg:
            print(f"    FVG: {fvg['tipo']} desde={fvg['desde']} hasta={fvg['hasta']}")
        else:
            print(f"    FVG: ninguno (confirmacion adicional -- no bloquea)")

        # PASO 8: barrida local M1 (confirmacion adicional -- no bloquea)
        barrida = detectar_barrida_previa(df_m1, evento, direccion_ev, lookback=BARRIDA_LOOKBACK_M1)
        print(f"    barrida: {'SI' if barrida else 'NO'}")

        # PASO 9: zona operativa SIEMPRE desde micro OB M1
        zona_desde = ob["desde"]
        zona_hasta = ob["hasta"]
        zona_size = abs(zona_hasta - zona_desde)

        # Validar que la zona esté en el lado correcto del precio
        zona_dict = {"zona_desde": zona_desde, "zona_hasta": zona_hasta}
        es_util, motivo_util, _ = validar_zona_operativa(symbol, zona_dict, precio_actual)

        print(f"    zona: [{zona_desde}, {zona_hasta}] size={round(zona_size, 4)}")
        print(f"    es_util: {es_util} ({motivo_util})")

        if not es_util:
            print(f"    SKIP: zona no util (precio no en lado correcto)")
            continue

        # Zona encontrada
        zona_encontrada = {
            "evento": evento,
            "ob": ob,
            "fvg": fvg,
            "barrida": barrida,
            "desplazamiento": desp,
            "zona_desde": zona_desde,
            "zona_hasta": zona_hasta,
            "zona_size": zona_size,
            "direccion": direccion_ev,
        }
        print(f"    ZONA ACEPTADA")
        break

    if not zona_encontrada:
        print(f"  SIN_SETUP: ningun candidato produjo zona micro valida")
        return _sin_setup(
            "SIN ZONA MICRO VALIDA EN M1",
            direccion_indice=direccion_indice,
            direccion_m15=direccion_m15,
            cumple_m15=True,
        )

    # ------------------------------------------------------------------
    # PASO 10: Score (0–6)
    # ------------------------------------------------------------------
    score = 0
    score += 1  # cumple M15 (ya validado)
    score += 1  # micro BOS/CHOCH alineado (ya validado)
    if zona_encontrada["barrida"]:
        score += 1
    if zona_encontrada["desplazamiento"]["valido"]:
        score += 1
    # OB siempre presente aquí (+1)
    score += 1
    if zona_encontrada["fvg"]:
        score += 1

    print(f"\n  SCORE: {score}/6")

    # ------------------------------------------------------------------
    # PASO 11: Verificar condiciones mínimas ACTIVA
    #   - cumple M15                   ✓ (ya pasó filtro)
    #   - micro BOS/CHOCH alineado     ✓ (ya pasó filtro)
    #   - desplazamiento impulsivo     ✓ (ya pasó en zona_encontrada)
    #   - micro OB válido              ✓ (ya pasó en zona_encontrada)
    # ------------------------------------------------------------------
    ev = zona_encontrada["evento"]
    micro_bos_choch = ev["evento"]
    zona_desde = zona_encontrada["zona_desde"]
    zona_hasta = zona_encontrada["zona_hasta"]
    zona_size = zona_encontrada["zona_size"]
    direccion = zona_encontrada["direccion"]

    has_ob = True
    has_fvg = zona_encontrada["fvg"] is not None
    has_barrida = zona_encontrada["barrida"] is not None
    has_desp = zona_encontrada["desplazamiento"]["valido"]

    # ------------------------------------------------------------------
    # PASO 12: TP/SL 1:2 y entrada
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

    Parte 2: lógica completa con filtro M15, micro BOS/CHOCH, barrida,
             OB, FVG, desplazamiento, TP/SL 1:2 y estados ACTIVA/SIN SETUP.

    Parte 3 (pendiente): estados EN_ZONA, PROFIT, TP, SL, PAUSADA, DESCARTADA
                         y modo seguimiento con Supabase.
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
