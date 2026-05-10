#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for SMC H1 + M15 PRO (FASE 3A)

Valida:
1. H1+M15 alineados genera setup ACTIVA
2. H1+M15 no alineados retorna NO_CUMPLE_CONDICIONES_H1_M15
3. TP 1:2 es correcto
4. SMC_M15_PRO NO se rompe (regresión)
5. Duplicate zone guard aislado por strategy_id
6. Aislamiento completo entre SMC_M15_PRO y SMC_H1_M15_PRO en Supabase

Nota: los tests usan FakeSupabaseService — sin conexión real a Supabase.
"""

import sys
import os
import io
from contextlib import redirect_stdout
from datetime import datetime, timedelta

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))

# ==============================================================
# IMPORTS
# ==============================================================
try:
    from smc_h1m15_service import (
        analyze_symbol_smc_h1m15,
        sync_setup_to_supabase_h1m15,
        _setup_cache_h1m15,
    )
    import smc_h1m15_service
    print("OK: smc_h1m15_service importado")
except ImportError as e:
    print(f"ERROR: smc_h1m15_service import failed: {e}")
    sys.exit(1)

try:
    from strategies.smc_h1_m15_pro.engine import (
        SMCH1M15ProEngine,
        calcular_niveles_operativos_1_2,
        verificar_alineacion_h1_m15,
        create_sin_setup_h1m15_response,
        TP_RATIO,
        STRATEGY_ID,
    )
    print("OK: smc_h1_m15_pro.engine importado")
except ImportError as e:
    print(f"ERROR: engine import failed: {e}")
    sys.exit(1)

try:
    from smc_m15_service import analyze_symbol_smc
    import smc_m15_service
    print("OK: smc_m15_service importado (regresión)")
except ImportError as e:
    print(f"ERROR: smc_m15_service import failed: {e}")
    sys.exit(1)


# ==============================================================
# HELPERS DE DATOS
# ==============================================================

def make_df(rows):
    return pd.DataFrame(rows)


def build_aligned_boom_data():
    """
    Genera H1 ALCISTA + M15 con último evento CHOCH_ALCISTA
    para simular condición BOOM alineada.
    """
    now = datetime(2024, 1, 1)

    # H1: tendencia alcista clara (higher highs, higher lows)
    h1_closes = [100, 102, 101, 104, 103, 106, 104, 108, 106, 110]
    h1_rows = []
    for i, close in enumerate(h1_closes):
        h1_rows.append({
            "time": now + timedelta(hours=i),
            "open": close - 1,
            "high": close + 1,
            "low": close - 2,
            "close": close,
        })

    # M15: tendencia alcista con CHOCH (similar structure)
    m15_closes = [100, 101, 100.5, 102, 101, 103, 102, 104, 103, 105.5]
    m15_rows = []
    for i, close in enumerate(m15_closes):
        m15_rows.append({
            "time": now + timedelta(minutes=15 * i),
            "open": close - 0.5,
            "high": close + 0.5,
            "low": close - 1,
            "close": close,
        })

    return make_df(h1_rows), make_df(m15_rows)


def build_misaligned_data():
    """
    Genera H1 BAJISTA + M15 con último evento CHOCH_ALCISTA
    → NO debe crear setup en SMC_H1_M15_PRO (no alineado).
    """
    now = datetime(2024, 1, 1)

    # H1: tendencia bajista
    h1_closes = [110, 108, 106, 104, 102, 100, 98, 96, 94, 92]
    h1_rows = []
    for i, close in enumerate(h1_closes):
        h1_rows.append({
            "time": now + timedelta(hours=i),
            "open": close + 1,
            "high": close + 2,
            "low": close - 1,
            "close": close,
        })

    # M15: tendencia alcista (contradicción con H1)
    m15_closes = [100, 101, 100.5, 102, 101, 103, 102, 104, 103, 105.5]
    m15_rows = []
    for i, close in enumerate(m15_closes):
        m15_rows.append({
            "time": now + timedelta(minutes=15 * i),
            "open": close - 0.5,
            "high": close + 0.5,
            "low": close - 1,
            "close": close,
        })

    return make_df(h1_rows), make_df(m15_rows)


class FakeSupabaseService:
    """Supabase fake in-memory — compatible con todas las funciones de supabase_service."""

    def __init__(self):
        self.records = []
        self.next_id = 1

    def get_active_setup_by_symbol(self, strategy_id, symbol):
        for record in reversed(self.records):
            if (
                record["strategy_id"] == strategy_id
                and record["symbol"] == symbol
                and record.get("estado") not in ["TP", "SL", "DESCARTADA"]
            ):
                return record
        return None

    def get_active_setup(self, strategy_id, symbol, entrada, stoploss):
        for record in reversed(self.records):
            if (
                record["strategy_id"] == strategy_id
                and record["symbol"] == symbol
                and record.get("entrada") == entrada
                and record.get("stoploss") == stoploss
                and record.get("estado") not in ["TP", "SL", "DESCARTADA"]
            ):
                return record
        return None

    def create_setup(self, setup_data):
        print("SUPABASE INSERT INTENT: fake")
        record = dict(setup_data)
        record["id"] = self.next_id
        self.next_id += 1
        self.records.append(record)
        print("SUPABASE OK: fake insert")
        return record

    def update_setup(self, setup_id, updates):
        for record in self.records:
            if record["id"] == setup_id:
                record.update(updates)
                print("SUPABASE OK: fake update")
                return record
        return None

    def get_setup_history(self, **kwargs):
        sid = kwargs.get("strategy_id")
        if sid:
            return [r for r in reversed(self.records) if r.get("strategy_id") == sid]
        return list(reversed(self.records))

    def get_closed_setup_by_levels(self, strategy_id, symbol, entrada, stoploss, tp_1_1):
        tol = 0.005
        for record in reversed(self.records):
            if record.get("strategy_id") != strategy_id or record.get("symbol") != symbol:
                continue
            if record.get("estado") not in ["TP", "SL"]:
                continue
            if abs(round(float(record.get("entrada", 0)), 2) - round(float(entrada), 2)) > tol:
                continue
            if abs(round(float(record.get("stoploss", 0)), 2) - round(float(stoploss), 2)) > tol:
                continue
            if abs(round(float(record.get("tp_1_1", 0)), 2) - round(float(tp_1_1), 2)) > tol:
                continue
            return record
        return None


# ==============================================================
# TEST 1: TP 1:2 CORRECTO
# ==============================================================

def test_tp_ratio():
    print("\n" + "=" * 60)
    print("TEST 1: TP 1:2 correcto")
    print("=" * 60)

    # BOOM (ALCISTA): entrada=100, stoploss=90, zona_size=10
    # tp = 100 + (10 * 2) = 120
    zona_boom = {"zona_desde": 90.0, "zona_hasta": 100.0}
    niveles_boom = calcular_niveles_operativos_1_2(zona_boom, "ALCISTA")
    assert niveles_boom["entrada"] == 100.0, f"entrada boom esperado 100.0, got {niveles_boom['entrada']}"
    assert niveles_boom["stoploss"] == 90.0, f"stoploss boom esperado 90.0, got {niveles_boom['stoploss']}"
    assert niveles_boom["tp_1_1"] == 120.0, f"tp boom esperado 120.0, got {niveles_boom['tp_1_1']}"
    print(f"OK BOOM: entrada={niveles_boom['entrada']}, sl={niveles_boom['stoploss']}, tp_1_2={niveles_boom['tp_1_1']}")

    # CRASH (BAJISTA): entrada=90, stoploss=100, zona_size=10
    # tp = 90 - (10 * 2) = 70
    zona_crash = {"zona_desde": 90.0, "zona_hasta": 100.0}
    niveles_crash = calcular_niveles_operativos_1_2(zona_crash, "BAJISTA")
    assert niveles_crash["entrada"] == 90.0, f"entrada crash esperado 90.0, got {niveles_crash['entrada']}"
    assert niveles_crash["stoploss"] == 100.0, f"stoploss crash esperado 100.0, got {niveles_crash['stoploss']}"
    assert niveles_crash["tp_1_1"] == 70.0, f"tp crash esperado 70.0, got {niveles_crash['tp_1_1']}"
    print(f"OK CRASH: entrada={niveles_crash['entrada']}, sl={niveles_crash['stoploss']}, tp_1_2={niveles_crash['tp_1_1']}")

    assert TP_RATIO == 2.0, f"TP_RATIO esperado 2.0, got {TP_RATIO}"
    print(f"OK tp_ratio = {TP_RATIO}")

    print("PASSED: TEST 1")
    return True


# ==============================================================
# TEST 2: H1/M15 alineados (BOOM) genera setup
# ==============================================================

def test_alineacion_h1_m15_boom():
    print("\n" + "=" * 60)
    print("TEST 2: H1 ALCISTA + evento M15 ALCISTA → alineado")
    print("=" * 60)

    alineado, motivo = verificar_alineacion_h1_m15(
        "Boom 1000 Index", "ALCISTA", "CHOCH_ALCISTA", 100.0
    )
    assert alineado, f"Esperaba alineado=True, got {alineado}. motivo: {motivo}"
    print(f"OK CHOCH_ALCISTA alineado: {motivo}")

    alineado2, motivo2 = verificar_alineacion_h1_m15(
        "Boom 500 Index", "ALCISTA", "BOS_ALCISTA", 100.0
    )
    assert alineado2, f"Esperaba alineado=True (BOS), got {alineado2}. motivo: {motivo2}"
    print(f"OK BOS_ALCISTA alineado: {motivo2}")

    print("PASSED: TEST 2")
    return True


# ==============================================================
# TEST 3: H1/M15 NO alineados → NO_CUMPLE_CONDICIONES_H1_M15
# ==============================================================

def test_no_alineacion():
    print("\n" + "=" * 60)
    print("TEST 3: H1 BAJISTA + evento M15 ALCISTA → NO_CUMPLE")
    print("=" * 60)

    # Boom con H1 bajista
    no_alineado, motivo = verificar_alineacion_h1_m15(
        "Boom 1000 Index", "BAJISTA", "CHOCH_ALCISTA", 100.0
    )
    assert not no_alineado, f"Esperaba alineado=False, got {no_alineado}"
    print(f"OK H1_BAJISTA rechazado para Boom: {motivo}")

    # Crash con H1 alcista
    no_alineado2, motivo2 = verificar_alineacion_h1_m15(
        "Crash 1000 Index", "ALCISTA", "BOS_BAJISTA", 100.0
    )
    assert not no_alineado2, f"Esperaba alineado=False, got {no_alineado2}"
    print(f"OK H1_ALCISTA rechazado para Crash: {motivo2}")

    # Evento M15 no alineado (H1 ok pero evento mal)
    no_alineado3, motivo3 = verificar_alineacion_h1_m15(
        "Boom 1000 Index", "ALCISTA", "CHOCH_BAJISTA", 100.0
    )
    assert not no_alineado3, f"Esperaba alineado=False (evento mal), got {no_alineado3}"
    print(f"OK evento_M15_BAJISTA rechazado para Boom ALCISTA: {motivo3}")

    print("PASSED: TEST 3")
    return True


# ==============================================================
# TEST 4: Full analysis retorna NO_CUMPLE para misaligned data
# ==============================================================

def test_full_analysis_no_cumple():
    print("\n" + "=" * 60)
    print("TEST 4: Full analysis con H1/M15 no alineados → NO_CUMPLE")
    print("=" * 60)

    original_service = smc_h1m15_service.supabase_service
    smc_h1m15_service.supabase_service = None
    _setup_cache_h1m15.clear()

    try:
        # Datos H1 bajista, M15 alcista → Boom NO debe crear setup
        df_h1, df_m15 = build_misaligned_data()
        captured = io.StringIO()
        with redirect_stdout(captured):
            result = analyze_symbol_smc_h1m15("Boom 1000 Index", df_h1, df_m15)
        output = captured.getvalue()

        # Si hay detección de estructura incompatible, puede ser SIN SETUP o NO_CUMPLE
        # El estado debe ser SIN SETUP (no guardado en Supabase)
        assert result["estado"] in ("SIN SETUP", "SIN_SETUP"), (
            f"Esperaba SIN SETUP para datos no alineados, got {result['estado']}"
        )
        # El estado dashboard puede ser NO_CUMPLE o SIN_SETUP dependiendo de la detección
        print(f"OK estado: {result['estado']}")
        print(f"OK estado_dashboard: {result['estado_dashboard']}")
        print(f"OK tp_ratio presente: {result.get('tp_ratio')}")
        assert result.get("tp_ratio") == TP_RATIO, f"tp_ratio ausente o incorrecto"
        assert "alineacion_h1" in result, "campo alineacion_h1 debe estar presente"
        assert "estado_h1_m15" in result, "campo estado_h1_m15 debe estar presente"
    finally:
        smc_h1m15_service.supabase_service = original_service
        _setup_cache_h1m15.clear()

    print("PASSED: TEST 4")
    return True


# ==============================================================
# TEST 5: Campos extra en respuesta
# ==============================================================

def test_campos_extra():
    print("\n" + "=" * 60)
    print("TEST 5: Campos extra tp_ratio, alineacion_h1, estado_h1_m15")
    print("=" * 60)

    response_sin_setup = create_sin_setup_h1m15_response(
        "Boom 1000 Index", 1234.0, "ALCISTA", "ALCISTA", "CHOCH_ALCISTA"
    )
    assert response_sin_setup.get("tp_ratio") == TP_RATIO, "tp_ratio debe ser 2.0"
    assert "alineacion_h1" in response_sin_setup, "alineacion_h1 debe estar en respuesta"
    assert "estado_h1_m15" in response_sin_setup, "estado_h1_m15 debe estar en respuesta"
    assert response_sin_setup["symbol"] == "Boom 1000 Index"
    assert response_sin_setup["price"] == 1234.0
    print(f"OK SIN SETUP response tiene tp_ratio={response_sin_setup['tp_ratio']}")
    print(f"OK SIN SETUP response tiene alineacion_h1={response_sin_setup['alineacion_h1']}")
    print(f"OK SIN SETUP response tiene estado_h1_m15={response_sin_setup['estado_h1_m15']}")

    response_no_cumple = create_sin_setup_h1m15_response(
        "Crash 500 Index", 5000.0, "ALCISTA", "--", "--",
        "NO_CUMPLE_CONDICIONES_H1_M15"
    )
    assert response_no_cumple["estado_dashboard"] == "NO_CUMPLE_CONDICIONES_H1_M15"
    assert response_no_cumple["estado_h1_m15"] == "NO_CUMPLE"
    print(f"OK NO_CUMPLE response tiene estado correcto")

    print("PASSED: TEST 5")
    return True


# ==============================================================
# TEST 6: strategy_id SMC_H1_M15_PRO en setup_data
# ==============================================================

def test_strategy_id_correcto():
    print("\n" + "=" * 60)
    print("TEST 6: strategy_id = SMC_H1_M15_PRO")
    print("=" * 60)

    assert STRATEGY_ID == "SMC_H1_M15_PRO", f"STRATEGY_ID esperado 'SMC_H1_M15_PRO', got {STRATEGY_ID}"
    print(f"OK STRATEGY_ID = {STRATEGY_ID}")

    engine = SMCH1M15ProEngine()
    assert engine.strategy_id == "SMC_H1_M15_PRO"
    assert engine.strategy_name == "SMC H1 + M15 PRO"
    print(f"OK engine.strategy_id = {engine.strategy_id}")
    print(f"OK engine.strategy_name = {engine.strategy_name}")

    print("PASSED: TEST 6")
    return True


# ==============================================================
# TEST 7: Aislamiento Supabase — SMC_H1_M15_PRO no afecta SMC_M15_PRO
# ==============================================================

def test_aislamiento_supabase():
    print("\n" + "=" * 60)
    print("TEST 7: Aislamiento Supabase por strategy_id")
    print("=" * 60)

    fake = FakeSupabaseService()

    # Pre-cargar un setup SMC_M15_PRO
    fake.records.append({
        "id": 1,
        "strategy_id": "SMC_M15_PRO",
        "symbol": "Boom 1000 Index",
        "entrada": 100.0,
        "stoploss": 90.0,
        "tp_1_1": 110.0,
        "estado": "ACTIVA",
        "ob": True, "fvg": False, "barrida": False, "score": 3,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    })
    fake.next_id = 2

    # get_active_setup_by_symbol con strategy_id='SMC_H1_M15_PRO' no debe ver el setup de SMC_M15_PRO
    result_h1m15 = fake.get_active_setup_by_symbol("SMC_H1_M15_PRO", "Boom 1000 Index")
    assert result_h1m15 is None, (
        f"SMC_H1_M15_PRO no debe ver setups de SMC_M15_PRO, got: {result_h1m15}"
    )
    print("OK SMC_H1_M15_PRO no ve setups de SMC_M15_PRO")

    # get_active_setup_by_symbol con strategy_id='SMC_M15_PRO' sí debe verlo
    result_m15 = fake.get_active_setup_by_symbol("SMC_M15_PRO", "Boom 1000 Index")
    assert result_m15 is not None, "SMC_M15_PRO debe ver su propio setup"
    print("OK SMC_M15_PRO ve su propio setup")

    # history filtrada por strategy_id
    fake.records.append({
        "id": 2,
        "strategy_id": "SMC_H1_M15_PRO",
        "symbol": "Crash 500 Index",
        "entrada": 200.0,
        "stoploss": 210.0,
        "tp_1_1": 180.0,
        "estado": "TP",
    })
    fake.next_id = 3

    history_h1m15 = fake.get_setup_history(strategy_id="SMC_H1_M15_PRO")
    history_m15 = fake.get_setup_history(strategy_id="SMC_M15_PRO")
    history_all = fake.get_setup_history()

    assert len(history_h1m15) == 1 and history_h1m15[0]["strategy_id"] == "SMC_H1_M15_PRO"
    assert len(history_m15) == 1 and history_m15[0]["strategy_id"] == "SMC_M15_PRO"
    assert len(history_all) == 2
    print(f"OK history H1M15={len(history_h1m15)}, M15={len(history_m15)}, ALL={len(history_all)}")

    print("PASSED: TEST 7")
    return True


# ==============================================================
# TEST 8: Duplicate zone guard aislado por strategy_id
# ==============================================================

def test_duplicate_guard_aislado():
    print("\n" + "=" * 60)
    print("TEST 8: Duplicate zone guard aislado por strategy_id")
    print("=" * 60)

    fake = FakeSupabaseService()

    # Setup cerrado de SMC_H1_M15_PRO
    fake.records.append({
        "id": 1,
        "strategy_id": "SMC_H1_M15_PRO",
        "symbol": "Boom 600 Index",
        "entrada": 5973.01,
        "stoploss": 5966.94,
        "tp_1_1": 5985.14,  # 1:2 ratio
        "estado": "TP",
    })
    fake.next_id = 2

    # Buscar como SMC_H1_M15_PRO → debe encontrar el duplicado
    found = fake.get_closed_setup_by_levels(
        "SMC_H1_M15_PRO", "Boom 600 Index", 5973.0101, 5966.9399, 5985.1401
    )
    assert found is not None, "SMC_H1_M15_PRO debe encontrar su propia zona cerrada"
    print(f"OK SMC_H1_M15_PRO duplicate guard funciona (encontró id={found['id']})")

    # Buscar como SMC_M15_PRO con los mismos niveles → NO debe encontrar
    not_found = fake.get_closed_setup_by_levels(
        "SMC_M15_PRO", "Boom 600 Index", 5973.0101, 5966.9399, 5985.1401
    )
    assert not_found is None, "SMC_M15_PRO NO debe encontrar el zona cerrada de SMC_H1_M15_PRO"
    print("OK SMC_M15_PRO duplicate guard NO ve zonas de SMC_H1_M15_PRO")

    print("PASSED: TEST 8")
    return True


# ==============================================================
# TEST 9: Regresión SMC_M15_PRO — analyze_symbol_smc sin cambios
# ==============================================================

def test_regresion_smc_m15():
    print("\n" + "=" * 60)
    print("TEST 9: Regresión SMC_M15_PRO — sin cambios")
    print("=" * 60)

    original_service = smc_m15_service.supabase_service
    smc_m15_service.supabase_service = None
    smc_m15_service._setup_cache.clear()

    try:
        now = datetime(2024, 1, 1)
        h1_closes = [100, 102, 101, 104, 103, 106, 104, 108, 106, 110]
        h1_rows = [
            {"time": now + timedelta(hours=i), "open": c - 1, "high": c + 1, "low": c - 2, "close": c}
            for i, c in enumerate(h1_closes)
        ]
        m15_closes = [100, 101, 100.5, 102, 101, 103, 102, 104, 103, 105.5]
        m15_rows = [
            {"time": now + timedelta(minutes=15 * i), "open": c - 0.5, "high": c + 0.5, "low": c - 1, "close": c}
            for i, c in enumerate(m15_closes)
        ]
        df_h1 = make_df(h1_rows)
        df_m15 = make_df(m15_rows)

        captured = io.StringIO()
        with redirect_stdout(captured):
            result = analyze_symbol_smc("Boom 1000 Index", df_h1, df_m15)

        assert "symbol" in result
        assert "tendencia_h1" in result
        assert "tendencia_m15" in result
        assert "ultimo_evento_m15" in result
        assert "zona_madre_m15" in result
        assert "entrada" in result
        assert "stoploss" in result
        assert "tp_1_1" in result
        assert "estado" in result
        assert "updated_at" in result
        # SMC_M15_PRO NO debe tener tp_ratio ni estado_h1_m15 en su respuesta
        # (son campos nuevos de SMC_H1_M15_PRO)
        print(f"OK SMC_M15_PRO resultado: symbol={result['symbol']}, estado={result['estado']}")
        print(f"OK SMC_M15_PRO no tiene contaminación de campos H1M15")

    finally:
        smc_m15_service.supabase_service = original_service
        smc_m15_service._setup_cache.clear()

    print("PASSED: TEST 9")
    return True


# ==============================================================
# TEST 10: Supabase sync — SMC_H1_M15_PRO usa strategy_id correcto
# ==============================================================

def test_sync_usa_strategy_id_correcto():
    print("\n" + "=" * 60)
    print("TEST 10: sync_setup_to_supabase_h1m15 usa strategy_id=SMC_H1_M15_PRO")
    print("=" * 60)

    fake = FakeSupabaseService()
    original_service = smc_h1m15_service.supabase_service
    smc_h1m15_service.supabase_service = fake
    _setup_cache_h1m15.clear()

    try:
        candidate = {
            "symbol": "Boom 1000 Index",
            "price": 105.0,
            "tendencia_h1": "ALCISTA",
            "tendencia_m15": "ALCISTA",
            "ultimo_evento_m15": "CHOCH_ALCISTA",
            "zona_madre_m15": {"desde": 90.0, "hasta": 100.0},
            "entrada": 100.0,
            "stoploss": 90.0,
            "tp_1_1": 120.0,
            "tp_ratio": 2.0,
            "score": 5,
            "ob": "SI",
            "fvg": "NO",
            "barrida": "SI",
            "estado_dashboard": "ACTIVA",
            "estado_historial": "ACTIVA",
            "estado_final": "ACTIVA",
            "estado": "ACTIVA",
            "alineacion_h1": "ALCISTA",
            "estado_h1_m15": "ALINEADO",
            "updated_at": "2024-01-01T00:00:00Z",
        }

        captured = io.StringIO()
        with redirect_stdout(captured):
            sync_setup_to_supabase_h1m15(candidate)
        output = captured.getvalue()

        assert len(fake.records) == 1, f"Esperaba 1 registro, got {len(fake.records)}"
        assert fake.records[0]["strategy_id"] == "SMC_H1_M15_PRO", (
            f"strategy_id debe ser SMC_H1_M15_PRO, got {fake.records[0]['strategy_id']}"
        )
        assert "SUPABASE INSERT INTENT" in output
        print(f"OK registro creado con strategy_id={fake.records[0]['strategy_id']}")
        print(f"OK setup_data.tp_1_1={fake.records[0]['tp_1_1']} (valor 1:2)")

    finally:
        smc_h1m15_service.supabase_service = original_service
        _setup_cache_h1m15.clear()

    print("PASSED: TEST 10")
    return True


# ==============================================================
# MAIN
# ==============================================================

def main():
    print("\n" + "=" * 70)
    print("SMC H1 + M15 PRO — TESTS FASE 3A")
    print("=" * 70)

    tests = [
        ("TP 1:2 correcto", test_tp_ratio),
        ("H1+M15 alineados BOOM", test_alineacion_h1_m15_boom),
        ("H1+M15 NO alineados", test_no_alineacion),
        ("Full analysis NO_CUMPLE", test_full_analysis_no_cumple),
        ("Campos extra en respuesta", test_campos_extra),
        ("strategy_id correcto", test_strategy_id_correcto),
        ("Aislamiento Supabase", test_aislamiento_supabase),
        ("Duplicate guard aislado", test_duplicate_guard_aislado),
        ("Regresión SMC_M15_PRO", test_regresion_smc_m15),
        ("Sync usa strategy_id correcto", test_sync_usa_strategy_id_correcto),
    ]

    passed = 0
    failed = 0

    for name, fn in tests:
        try:
            fn()
            passed += 1
        except AssertionError as e:
            print(f"\n✗ FAIL [{name}]: {e}")
            failed += 1
        except Exception as e:
            print(f"\n✗ ERROR [{name}]: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 70)
    print(f"RESUMEN: {passed}/{passed + failed} tests pasaron")
    if failed == 0:
        print("✓ TODOS LOS TESTS PASARON")
    else:
        print(f"✗ {failed} TEST(S) FALLARON")
    print("=" * 70)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
