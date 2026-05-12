#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test suite: SMC_MICRO_IMPULSO_FILTRADO_M15 TP/SL sync behaviour.

Valida que sync_setup_filtrado_m15() cierre correctamente los registros
activos al recibir estados terminales TP o SL desde la base MICRO IMPULSO.

Casos:
  1. CASO SL  — registro ACTIVA → update a SL con resultado/motivo_cierre.
  2. CASO TP  — registro ACTIVA → update a TP con resultado/motivo_cierre.
  3. DEBOUNCE — aunque _has_relevant_changes devuelva False, TP/SL actualiza.
  4. PAUSADA_NUEVA_HELPER — PAUSADA ya no es devuelta por get_open_filtrado_m15_setup
                             → TP sin open record → SKIP (no update, no create).
  5. PAUSADA_NO_COINCIDE — mismo resultado: no open record → SKIP.
  6. TERMINAL_SIN_REGISTRO — SL sin registro activo → SKIP, no crea nuevo.
  7. LLEGANDO_A_ZONA — registro en LLEGANDO_A_ZONA se cierra como SL.
  8. updates NO contiene estado_historial ni estado_final (columnas inexistentes).
  9. updates SÍ contiene resultado, resultado_puntos, motivo_cierre para TP/SL.
 10. py_compile OK para smc_micro_impulso_filtrado_m15_service.py.
 11. LLEGANDO_A_ZONA → EN_ZONA.
 12. Estado no terminal (ACTIVA → LLEGANDO_A_ZONA).
 13. EN_ZONA persiste aunque engine base devuelva SIN_SETUP (escenario real de bug).
 14. get_open_filtrado_m15_setup es llamado; get_active_setup_by_symbol NO.
 15. get_open_filtrado_m15_setup acepta ACTIVA/LLEGANDO_A_ZONA/EN_ZONA/PROFIT;
     nunca devuelve TP/SL/DESCARTADA/PAUSADA (validado por helper).
 16. EN_ZONA update: niveles entrada/stoploss/tp se mantienen (no sobreescribe).
"""

import sys
import os
import py_compile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ─── Test helpers ────────────────────────────────────────────────────────────

_passed = 0
_failed = 0


def assert_true(condition, msg):
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"  OK: {msg}")
    else:
        _failed += 1
        print(f"  FAIL: {msg}")


def assert_equal(a, b, msg):
    assert_true(a == b, f"{msg} (got {a!r}, expected {b!r})")


def assert_none(val, msg):
    assert_true(val is None, f"{msg} (got {val!r})")


def assert_not_none(val, msg):
    assert_true(val is not None, msg)


def assert_in(val, container, msg):
    assert_true(val in container, f"{msg} (got {val!r})")


def assert_not_in(val, container, msg):
    assert_true(val not in container, f"{msg} ({val!r} found but should not be)")


# ─── Fake Supabase service ────────────────────────────────────────────────────

class FakeSupabaseService:
    """Fake Supabase service that records calls and simulates DB state."""

    def __init__(self, active_setup_by_symbol=None, closed_setup=None,
                 open_filtrado_setup=None):
        self._active_setup_by_symbol = active_setup_by_symbol
        self._closed_setup = closed_setup
        # open_filtrado_setup: returned by get_open_filtrado_m15_setup
        # Only includes ACTIVA/LLEGANDO_A_ZONA/EN_ZONA/PROFIT records.
        self._open_filtrado_setup = open_filtrado_setup
        self.calls = []

    def get_active_setup_by_symbol(self, strategy_id, symbol):
        self.calls.append(("get_active_setup_by_symbol", strategy_id, symbol))
        return self._active_setup_by_symbol

    def get_open_filtrado_m15_setup(self, symbol, entrada=None, stoploss=None):
        self.calls.append(("get_open_filtrado_m15_setup", symbol, entrada, stoploss))
        return self._open_filtrado_setup

    def get_closed_setup_by_levels(self, strategy_id, symbol, entrada, stoploss, tp):
        self.calls.append(("get_closed_setup_by_levels", strategy_id, symbol))
        return self._closed_setup

    def update_setup(self, setup_id, updates):
        self.calls.append(("update_setup", setup_id, updates))
        return {"id": setup_id, **updates}

    def create_setup(self, setup_data):
        self.calls.append(("create_setup", setup_data))
        return {"id": "new-id", **setup_data}

    def reset(self):
        self.calls = []

    def update_calls(self):
        return [c for c in self.calls if c[0] == "update_setup"]

    def create_calls(self):
        return [c for c in self.calls if c[0] == "create_setup"]


# ─── Import target ────────────────────────────────────────────────────────────

import smc_micro_impulso_filtrado_m15_service as svc_mod

SERVICE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "smc_micro_impulso_filtrado_m15_service.py",
)


def _make_result(
    symbol="Boom 1000 Index",
    estado="ACTIVA",
    estado_dashboard="ACTIVA",
    entrada=100.0,
    stoploss=90.0,
    tp_1_1=120.0,
    precio_actual=95.0,
    tp_puntos=20.0,
    sl_puntos=10.0,
    direccion_m15="ALCISTA",
    score=3,
    zona_desde=89.0,
    zona_hasta=91.0,
):
    return {
        "symbol": symbol,
        "estado": estado,
        "estado_dashboard": estado_dashboard,
        "entrada": entrada,
        "stoploss": stoploss,
        "tp": tp_1_1,
        "tp_1_1": tp_1_1,
        "precio_actual": precio_actual,
        "price": precio_actual,
        "tp_puntos": tp_puntos,
        "sl_puntos": sl_puntos,
        "direccion_m15": direccion_m15,
        "score": score,
        "zona_desde": zona_desde,
        "zona_hasta": zona_hasta,
        "micro_bos_choch": "--",
        "ob": "NO",
        "fvg": "NO",
        "barrida": "NO",
    }


def _inject_fake_supabase(fake):
    """Replace the module-level supabase_service with a fake instance."""
    svc_mod.supabase_service = fake


def _clear_cache(symbol="Boom 1000 Index"):
    svc_mod._setup_cache_micro_impulso_filtrado_m15.pop(symbol, None)


# ─── TESTS ────────────────────────────────────────────────────────────────────

def test_py_compile():
    """Test 10: smc_micro_impulso_filtrado_m15_service.py compila sin errores."""
    print("\n--- test_py_compile ---")
    try:
        py_compile.compile(SERVICE_FILE, doraise=True)
        assert_true(True, "py_compile OK")
    except py_compile.PyCompileError as e:
        assert_true(False, f"py_compile FAIL: {e}")


def test_sl_closes_activa_record():
    """Test 1: SL llega con registro ACTIVA → update a SL con resultado/motivo_cierre."""
    print("\n--- test_sl_closes_activa_record ---")

    existing = {
        "id": "setup-sl-1",
        "estado": "ACTIVA",
        "entrada": 100.0,
        "stoploss": 90.0,
        "tp_1_1": 120.0,
    }
    fake = FakeSupabaseService(open_filtrado_setup=existing)
    _inject_fake_supabase(fake)
    _clear_cache()

    result = _make_result(estado="SL", estado_dashboard="SL", precio_actual=89.0)
    svc_mod.sync_setup_filtrado_m15(result)

    updates_calls = fake.update_calls()
    assert_equal(len(updates_calls), 1, "update_setup llamado exactamente 1 vez")

    _, called_id, updates = updates_calls[0]
    assert_equal(called_id, "setup-sl-1", "update_setup llamado sobre el id correcto")
    assert_equal(updates.get("estado"), "SL", "updates['estado'] = 'SL'")
    assert_equal(updates.get("estado_dashboard"), "SL", "updates['estado_dashboard'] = 'SL'")
    assert_equal(updates.get("resultado"), "SL", "updates['resultado'] = 'SL'")
    assert_true(
        "SL" in str(updates.get("motivo_cierre", "")),
        "motivo_cierre contiene 'SL'",
    )
    assert_equal(len(fake.create_calls()), 0, "create_setup NO fue llamado")


def test_tp_closes_activa_record():
    """Test 2: TP llega con registro ACTIVA → update a TP con resultado/motivo_cierre."""
    print("\n--- test_tp_closes_activa_record ---")

    existing = {
        "id": "setup-tp-1",
        "estado": "ACTIVA",
        "entrada": 100.0,
        "stoploss": 90.0,
        "tp_1_1": 120.0,
    }
    fake = FakeSupabaseService(open_filtrado_setup=existing)
    _inject_fake_supabase(fake)
    _clear_cache()

    result = _make_result(estado="TP", estado_dashboard="TP", precio_actual=121.0)
    svc_mod.sync_setup_filtrado_m15(result)

    updates_calls = fake.update_calls()
    assert_equal(len(updates_calls), 1, "update_setup llamado exactamente 1 vez")

    _, called_id, updates = updates_calls[0]
    assert_equal(called_id, "setup-tp-1", "update_setup llamado sobre el id correcto")
    assert_equal(updates.get("estado"), "TP", "updates['estado'] = 'TP'")
    assert_equal(updates.get("estado_dashboard"), "TP", "updates['estado_dashboard'] = 'TP'")
    assert_equal(updates.get("resultado"), "TP", "updates['resultado'] = 'TP'")
    assert_true(
        "TP" in str(updates.get("motivo_cierre", "")),
        "motivo_cierre contiene 'TP'",
    )
    assert_equal(len(fake.create_calls()), 0, "create_setup NO fue llamado")


def test_debounce_bypass_for_terminal_state():
    """Test 3: aunque _has_relevant_changes devuelva False, TP/SL actualiza igual."""
    print("\n--- test_debounce_bypass_for_terminal_state ---")

    existing = {
        "id": "setup-debounce-1",
        "estado": "ACTIVA",
        "entrada": 100.0,
        "stoploss": 90.0,
        "tp_1_1": 120.0,
    }
    fake = FakeSupabaseService(open_filtrado_setup=existing)
    _inject_fake_supabase(fake)

    symbol = "Boom 1000 Index"
    # Pre-seed cache with the exact same critical_data → _has_relevant_changes returns False
    svc_mod._setup_cache_micro_impulso_filtrado_m15[symbol] = {
        "estado": "TP",
        "entrada": 100.0,
        "stoploss": 90.0,
        "tp_1_1": 120.0,
        "score": 3,
        "zona_desde": 89.0,
        "zona_hasta": 91.0,
        "precio_actual": 121.0,
    }

    result = _make_result(estado="TP", estado_dashboard="TP", precio_actual=121.0)
    svc_mod.sync_setup_filtrado_m15(result)

    updates_calls = fake.update_calls()
    assert_equal(len(updates_calls), 1, "update_setup llamado a pesar de no haber cambios en cache")
    _, _, updates = updates_calls[0]
    assert_equal(updates.get("estado"), "TP", "updates['estado'] = 'TP' con debounce bypass")


def test_pausada_not_found_by_new_helper():
    """Test 4 (nuevo comportamiento): get_open_filtrado_m15_setup NUNCA devuelve PAUSADA.
    Cuando el único registro en Supabase es PAUSADA, el helper devuelve None.
    TP sin open record → SKIP (no update, no create).
    """
    print("\n--- test_pausada_not_found_by_new_helper ---")

    # El helper devuelve None porque PAUSADA no está en los estados abiertos permitidos.
    fake = FakeSupabaseService(open_filtrado_setup=None)
    _inject_fake_supabase(fake)
    _clear_cache()

    result = _make_result(estado="TP", estado_dashboard="TP", precio_actual=121.0)
    svc_mod.sync_setup_filtrado_m15(result)

    assert_equal(len(fake.update_calls()), 0, "update_setup NO llamado (sin open record para PAUSADA)")
    assert_equal(len(fake.create_calls()), 0, "create_setup NO llamado (estado terminal sin registro)")


def test_pausada_with_different_levels_skips():
    """Test 5: sin open record (PAUSADA nunca retornada) → SKIP igual que antes."""
    print("\n--- test_pausada_with_different_levels_skips ---")

    fake = FakeSupabaseService(open_filtrado_setup=None)
    _inject_fake_supabase(fake)
    _clear_cache()

    result = _make_result(estado="TP", estado_dashboard="TP", precio_actual=121.0)
    svc_mod.sync_setup_filtrado_m15(result)

    assert_equal(len(fake.update_calls()), 0, "update_setup NO llamado")
    assert_equal(len(fake.create_calls()), 0, "create_setup NO llamado (estado terminal sin registro)")


def test_terminal_without_existing_record_skips():
    """Test 6: SL sin registro activo → SKIP, no crear registro nuevo."""
    print("\n--- test_terminal_without_existing_record_skips ---")

    fake = FakeSupabaseService(open_filtrado_setup=None)
    _inject_fake_supabase(fake)
    _clear_cache()

    result = _make_result(estado="SL", estado_dashboard="SL", precio_actual=89.0)
    svc_mod.sync_setup_filtrado_m15(result)

    assert_equal(len(fake.update_calls()), 0, "update_setup NO llamado cuando no hay registro")
    assert_equal(len(fake.create_calls()), 0, "create_setup NO llamado para estado terminal sin registro")


def test_llegando_a_zona_closes_as_sl():
    """Test 7: registro en LLEGANDO_A_ZONA se cierra correctamente como SL."""
    print("\n--- test_llegando_a_zona_closes_as_sl ---")

    existing = {
        "id": "setup-llegando-1",
        "estado": "LLEGANDO_A_ZONA",
        "entrada": 100.0,
        "stoploss": 90.0,
        "tp_1_1": 120.0,
    }
    fake = FakeSupabaseService(open_filtrado_setup=existing)
    _inject_fake_supabase(fake)
    _clear_cache()

    result = _make_result(estado="SL", estado_dashboard="SL", precio_actual=89.0)
    svc_mod.sync_setup_filtrado_m15(result)

    updates_calls = fake.update_calls()
    assert_equal(len(updates_calls), 1, "update_setup llamado sobre registro LLEGANDO_A_ZONA")
    _, called_id, updates = updates_calls[0]
    assert_equal(called_id, "setup-llegando-1", "update sobre el id correcto")
    assert_equal(updates.get("estado"), "SL", "updates['estado'] = 'SL'")
    assert_equal(updates.get("resultado"), "SL", "updates['resultado'] = 'SL'")


def test_updates_no_invalid_columns():
    """Test 8: updates NO contiene estado_historial ni estado_final."""
    print("\n--- test_updates_no_invalid_columns ---")

    existing = {
        "id": "setup-cols-1",
        "estado": "ACTIVA",
        "entrada": 100.0,
        "stoploss": 90.0,
        "tp_1_1": 120.0,
    }
    fake = FakeSupabaseService(open_filtrado_setup=existing)
    _inject_fake_supabase(fake)
    _clear_cache()

    result = _make_result(estado="SL", estado_dashboard="SL", precio_actual=89.0)
    svc_mod.sync_setup_filtrado_m15(result)

    updates_calls = fake.update_calls()
    assert_equal(len(updates_calls), 1, "update_setup fue llamado")
    _, _, updates = updates_calls[0]
    assert_not_in("estado_historial", updates, "updates NO contiene 'estado_historial'")
    assert_not_in("estado_final", updates, "updates NO contiene 'estado_final'")


def test_updates_has_resultado_fields_for_tp_sl():
    """Test 9: updates SÍ contiene resultado, resultado_puntos, motivo_cierre para TP/SL."""
    print("\n--- test_updates_has_resultado_fields_for_tp_sl ---")

    existing = {
        "id": "setup-resultado-1",
        "estado": "ACTIVA",
        "entrada": 100.0,
        "stoploss": 90.0,
        "tp_1_1": 120.0,
    }
    fake = FakeSupabaseService(open_filtrado_setup=existing)
    _inject_fake_supabase(fake)
    _clear_cache()

    result = _make_result(
        estado="SL", estado_dashboard="SL", precio_actual=89.0,
        tp_puntos=20.0, sl_puntos=10.0,
    )
    svc_mod.sync_setup_filtrado_m15(result)

    updates_calls = fake.update_calls()
    assert_equal(len(updates_calls), 1, "update_setup llamado")
    _, _, updates = updates_calls[0]
    assert_in("resultado", updates, "updates contiene 'resultado'")
    assert_in("resultado_puntos", updates, "updates contiene 'resultado_puntos'")
    assert_in("motivo_cierre", updates, "updates contiene 'motivo_cierre'")
    # resultado_puntos debe ser negativo para SL (pérdida)
    rp = updates.get("resultado_puntos")
    assert_true(rp is not None and rp < 0, f"resultado_puntos es negativo para SL (got {rp})")

    # Ahora TP: debe ser positivo
    fake2 = FakeSupabaseService(open_filtrado_setup={
        "id": "setup-resultado-2",
        "estado": "ACTIVA",
        "entrada": 100.0,
        "stoploss": 90.0,
        "tp_1_1": 120.0,
    })
    _inject_fake_supabase(fake2)
    _clear_cache()

    result_tp = _make_result(
        estado="TP", estado_dashboard="TP", precio_actual=121.0,
        tp_puntos=20.0, sl_puntos=10.0,
    )
    svc_mod.sync_setup_filtrado_m15(result_tp)

    updates_calls2 = fake2.update_calls()
    assert_equal(len(updates_calls2), 1, "update_setup llamado para TP")
    _, _, updates2 = updates_calls2[0]
    rp2 = updates2.get("resultado_puntos")
    assert_true(rp2 is not None and rp2 > 0, f"resultado_puntos es positivo para TP (got {rp2})")


def test_llegando_a_zona_to_en_zona():
    """
    Test obligatorio: LLEGANDO_A_ZONA → EN_ZONA.

    Supabase fake tiene registro con estado=LLEGANDO_A_ZONA y niveles completos.
    El engine recibe resultado con estado=EN_ZONA y precio dentro de zona (99).

    Esperado:
    - update_setup sobre el mismo id
    - estado = EN_ZONA
    - estado_dashboard = EN_ZONA
    - entrada, stoploss, tp_1_1 se mantienen en el registro
    - no create_setup
    - no SIN_SETUP
    """
    print("\n--- test_llegando_a_zona_to_en_zona ---")

    existing = {
        "id": "setup-llegando-en-zona-1",
        "estado": "LLEGANDO_A_ZONA",
        "entrada": 100.0,
        "stoploss": 90.0,
        "tp_1_1": 120.0,
        "zona_desde": 90.0,
        "zona_hasta": 100.0,
    }
    fake = FakeSupabaseService(open_filtrado_setup=existing)
    _inject_fake_supabase(fake)
    _clear_cache()

    # precio_actual=99 está dentro de la zona (90 ≤ 99 ≤ 100) → EN_ZONA
    result = _make_result(
        estado="EN_ZONA",
        estado_dashboard="EN_ZONA",
        precio_actual=99.0,
        entrada=100.0,
        stoploss=90.0,
        tp_1_1=120.0,
        zona_desde=90.0,
        zona_hasta=100.0,
    )
    svc_mod.sync_setup_filtrado_m15(result)

    updates_calls = fake.update_calls()
    assert_equal(len(updates_calls), 1, "update_setup llamado exactamente 1 vez")

    _, called_id, updates = updates_calls[0]
    assert_equal(called_id, "setup-llegando-en-zona-1", "update sobre el mismo id (no nuevo)")
    assert_equal(updates.get("estado"), "EN_ZONA", "estado actualizado a EN_ZONA")
    assert_equal(updates.get("estado_dashboard"), "EN_ZONA", "estado_dashboard = EN_ZONA")
    assert_equal(len(fake.create_calls()), 0, "create_setup NO llamado (no nuevo registro)")
    assert_not_in("resultado", updates, "NO contiene resultado (no es terminal)")
    assert_not_in("motivo_cierre", updates, "NO contiene motivo_cierre (no es terminal)")


def test_non_terminal_state_still_works():
    """Sanity: estado no terminal (ACTIVA → LLEGANDO_A_ZONA) sigue actualizando."""
    print("\n--- test_non_terminal_state_still_works ---")

    existing = {
        "id": "setup-nt-1",
        "estado": "ACTIVA",
        "entrada": 100.0,
        "stoploss": 90.0,
        "tp_1_1": 120.0,
    }
    fake = FakeSupabaseService(open_filtrado_setup=existing)
    _inject_fake_supabase(fake)
    _clear_cache()

    result = _make_result(estado="LLEGANDO_A_ZONA", estado_dashboard="LLEGANDO_A_ZONA")
    svc_mod.sync_setup_filtrado_m15(result)

    updates_calls = fake.update_calls()
    assert_equal(len(updates_calls), 1, "update_setup llamado para transicion no-terminal")
    _, _, updates = updates_calls[0]
    assert_equal(updates.get("estado"), "LLEGANDO_A_ZONA", "estado actualizado a LLEGANDO_A_ZONA")
    assert_not_in("resultado", updates, "updates NO contiene resultado para estado no-terminal")
    assert_not_in("motivo_cierre", updates, "updates NO contiene motivo_cierre para estado no-terminal")


def test_en_zona_persists_when_base_returns_sin_setup():
    """
    Test 13 — CASO DEL BUG: EN_ZONA persiste aunque engine base devuelva SIN_SETUP.

    Supabase fake: registro existente con estado=EN_ZONA y niveles:
      entrada=5941.95, stoploss=5930.72, tp_1_1=5964.42.

    El service recibe resultado con estado=EN_ZONA (ya procesado por rescue path)
    y precio_actual=5989.34 (precio fuera de zona pero trade sigue vivo).

    Esperado:
    - update_setup sobre el mismo id (id="setup-en-zona-real")
    - estado = EN_ZONA
    - estado_dashboard = EN_ZONA
    - NO crea registro nuevo
    - NO devuelve SIN_SETUP (el llamador no pierde el trade)
    - entrada, stoploss, tp se preservan en los niveles correctos
    """
    print("\n--- test_en_zona_persists_when_base_returns_sin_setup ---")

    existing = {
        "id": "setup-en-zona-real",
        "estado": "EN_ZONA",
        "entrada": 5941.95,
        "stoploss": 5930.72,
        "tp_1_1": 5964.42,
    }
    # open_filtrado_setup devuelve el registro EN_ZONA (helper correcto)
    fake = FakeSupabaseService(open_filtrado_setup=existing)
    _inject_fake_supabase(fake)
    _clear_cache("Boom 1000 Index")

    # El service recibe estado=EN_ZONA (rescue path lo reconstruyó desde Supabase)
    result = _make_result(
        symbol="Boom 1000 Index",
        estado="EN_ZONA",
        estado_dashboard="EN_ZONA",
        entrada=5941.95,
        stoploss=5930.72,
        tp_1_1=5964.42,
        precio_actual=5989.34,
    )
    svc_mod.sync_setup_filtrado_m15(result)

    updates_calls = fake.update_calls()
    # Debe haber un update (no skip, no create)
    assert_equal(len(updates_calls), 1, "update_setup llamado: trade EN_ZONA rescatado")

    _, called_id, updates = updates_calls[0]
    assert_equal(called_id, "setup-en-zona-real", "update sobre el id correcto")
    assert_equal(updates.get("estado"), "EN_ZONA", "estado=EN_ZONA mantenido")
    assert_equal(updates.get("estado_dashboard"), "EN_ZONA", "estado_dashboard=EN_ZONA")
    assert_equal(len(fake.create_calls()), 0, "create_setup NO llamado")
    assert_not_in("resultado", updates, "NO contiene resultado (no es terminal)")


def test_get_open_filtrado_m15_setup_is_called_not_by_symbol():
    """
    Test 14: sync_setup_filtrado_m15 llama a get_open_filtrado_m15_setup y
    NO llama a get_active_setup_by_symbol (helper antiguo).
    """
    print("\n--- test_get_open_filtrado_m15_setup_is_called_not_by_symbol ---")

    existing = {
        "id": "setup-call-check-1",
        "estado": "PROFIT",
        "entrada": 100.0,
        "stoploss": 90.0,
        "tp_1_1": 120.0,
    }
    fake = FakeSupabaseService(open_filtrado_setup=existing)
    _inject_fake_supabase(fake)
    _clear_cache()

    result = _make_result(estado="PROFIT", estado_dashboard="PROFIT")
    svc_mod.sync_setup_filtrado_m15(result)

    open_calls = [c for c in fake.calls if c[0] == "get_open_filtrado_m15_setup"]
    assert_true(len(open_calls) >= 1, "get_open_filtrado_m15_setup fue llamado")

    by_symbol_calls = [c for c in fake.calls if c[0] == "get_active_setup_by_symbol"]
    assert_equal(len(by_symbol_calls), 0, "get_active_setup_by_symbol NO fue llamado")


def test_helper_open_states_filter():
    """
    Test 15: get_open_filtrado_m15_setup solo devuelve estados abiertos.

    Verifica que el FakeSupabaseService correctamente represente el contrato
    del helper: ACTIVA/LLEGANDO_A_ZONA/EN_ZONA/PROFIT son válidos; cuando
    open_filtrado_setup=None el servicio trata el trade como inexistente.

    También valida directamente la lista _FILTRADO_M15_OPEN_STATES en
    supabase_service.py.
    """
    print("\n--- test_helper_open_states_filter ---")

    import supabase_service as supa_mod

    OPEN_STATES = ["ACTIVA", "LLEGANDO_A_ZONA", "EN_ZONA", "PROFIT"]
    CLOSED_STATES = ["TP", "SL", "DESCARTADA", "PAUSADA"]

    for s in OPEN_STATES:
        assert_in(s, supa_mod._FILTRADO_M15_OPEN_STATES,
                  f"{s} debe estar en _FILTRADO_M15_OPEN_STATES")

    for s in CLOSED_STATES:
        assert_not_in(s, supa_mod._FILTRADO_M15_OPEN_STATES,
                      f"{s} NO debe estar en _FILTRADO_M15_OPEN_STATES")

    # Verificar que cuando fake devuelve None (PAUSADA/TP/SL no encontrado),
    # el sync no actualiza nada para estado terminal (SKIP_NO_EXISTING).
    fake = FakeSupabaseService(open_filtrado_setup=None)
    _inject_fake_supabase(fake)
    _clear_cache()

    for closed in ["TP", "SL"]:
        fake.calls.clear()
        result = _make_result(estado=closed, estado_dashboard=closed)
        svc_mod.sync_setup_filtrado_m15(result)
        assert_equal(len(fake.update_calls()), 0,
                     f"update NO llamado para {closed} sin open record")
        assert_equal(len(fake.create_calls()), 0,
                     f"create NO llamado para {closed} sin open record")


def test_en_zona_update_preserves_levels():
    """
    Test 16: update de EN_ZONA no sobreescribe entrada/stoploss/tp del registro.

    Los updates de estado no-terminal solo deben modificar:
    estado, estado_dashboard, precio_actual.
    Los niveles (entrada, stoploss, tp_1_1) se preservan en Supabase
    (no se incluyen en el dict de updates).
    """
    print("\n--- test_en_zona_update_preserves_levels ---")

    existing = {
        "id": "setup-levels-preserve-1",
        "estado": "LLEGANDO_A_ZONA",
        "entrada": 5941.95,
        "stoploss": 5930.72,
        "tp_1_1": 5964.42,
    }
    fake = FakeSupabaseService(open_filtrado_setup=existing)
    _inject_fake_supabase(fake)
    _clear_cache()

    result = _make_result(
        estado="EN_ZONA",
        estado_dashboard="EN_ZONA",
        entrada=5941.95,
        stoploss=5930.72,
        tp_1_1=5964.42,
        precio_actual=5939.00,
    )
    svc_mod.sync_setup_filtrado_m15(result)

    updates_calls = fake.update_calls()
    assert_equal(len(updates_calls), 1, "update_setup llamado")
    _, _, updates = updates_calls[0]

    # Los campos de niveles NO deben aparecer en updates (se preservan en DB)
    assert_not_in("entrada", updates, "updates NO sobreescribe 'entrada'")
    assert_not_in("stoploss", updates, "updates NO sobreescribe 'stoploss'")
    assert_not_in("tp_1_1", updates, "updates NO sobreescribe 'tp_1_1'")

    # Solo campos de estado y precio
    assert_in("estado", updates, "updates contiene 'estado'")
    assert_in("estado_dashboard", updates, "updates contiene 'estado_dashboard'")
    assert_in("precio_actual", updates, "updates contiene 'precio_actual'")


# ─── Runner ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("TEST: SMC_MICRO_IMPULSO_FILTRADO_M15 TP/SL SYNC")
    print("=" * 60)

    test_py_compile()
    test_sl_closes_activa_record()
    test_tp_closes_activa_record()
    test_debounce_bypass_for_terminal_state()
    test_pausada_not_found_by_new_helper()
    test_pausada_with_different_levels_skips()
    test_terminal_without_existing_record_skips()
    test_llegando_a_zona_closes_as_sl()
    test_updates_no_invalid_columns()
    test_updates_has_resultado_fields_for_tp_sl()
    test_llegando_a_zona_to_en_zona()
    test_non_terminal_state_still_works()
    test_en_zona_persists_when_base_returns_sin_setup()
    test_get_open_filtrado_m15_setup_is_called_not_by_symbol()
    test_helper_open_states_filter()
    test_en_zona_update_preserves_levels()

    print("\n" + "=" * 60)
    print(f"RESULTADO: {_passed} pasados, {_failed} fallados de {_passed + _failed} total")
    print("=" * 60)

    if _failed > 0:
        sys.exit(1)

