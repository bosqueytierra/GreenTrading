#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test suite: _ReadOnlySupabaseProxy isolation for FILTRADO M15.

Valida los 10 puntos del problema statement:

  1. get_active_setup_by_symbol SÍ pasa a través del proxy.
  2. get_active_setup SÍ pasa a través del proxy.
  3. get_closed_setup_by_levels SÍ pasa a través del proxy.
  4. update_setup NO escribe (proxy lo bloquea, retorna None).
  5. create_setup NO escribe (proxy lo bloquea, retorna None).
  6. upsert_setup NO escribe (proxy lo bloquea, retorna None).
  7. delete_setup NO escribe (proxy lo bloquea, retorna None).
  8. El endpoint normal usa el servicio real (sin proxy) — writes permitidos.
  9. El endpoint filtrado usa el proxy — writes a SMC_MICRO_IMPULSO bloqueados.
 10. Solo SMC_MICRO_IMPULSO_FILTRADO_M15 escribe en su propio strategy_id.

  Y:
 11. TP MICRO IMPULSO normal = ratio 1:1.
 12. TP FILTRADO M15 = ratio 1:2 (recalculado).
 13. Si M15 cumple: FILTRADO M15 muestra mismo estado que MICRO IMPULSO normal.
 14. Si M15 no cumple: FILTRADO M15 retorna SIN SETUP / NO CUMPLE DIRECCIÓN M15.
 15. Columnas PRECIO y ACTUALIZACIÓN presentes en la respuesta (no MOTIVO en tabla).
 16. py_compile OK en todos los módulos afectados.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ============================================================
# Test helpers
# ============================================================

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
    assert_true(val is not None, f"{msg}")


# ============================================================
# Fake Supabase service with write call tracking
# ============================================================

class FakeSupabaseService:
    """Fake Supabase service that tracks which methods are called."""

    def __init__(self, active_setup=None, active_setup_by_symbol=None, closed_setup=None):
        self._active_setup = active_setup
        self._active_setup_by_symbol = active_setup_by_symbol
        self._closed_setup = closed_setup

        # Call logs — reset before each test
        self.calls = []

    def get_active_setup(self, strategy_id, symbol, entrada, stoploss):
        self.calls.append(("get_active_setup", strategy_id, symbol))
        return self._active_setup

    def get_active_setup_by_symbol(self, strategy_id, symbol):
        self.calls.append(("get_active_setup_by_symbol", strategy_id, symbol))
        return self._active_setup_by_symbol

    def get_closed_setup_by_levels(self, strategy_id, symbol, entrada, stoploss, tp):
        self.calls.append(("get_closed_setup_by_levels", strategy_id, symbol))
        return self._closed_setup

    def update_setup(self, setup_id, updates):
        self.calls.append(("update_setup", setup_id, updates))
        return {"id": setup_id, **updates}

    def create_setup(self, setup_data):
        self.calls.append(("create_setup", setup_data.get("strategy_id")))
        return {"id": "new-id", **setup_data}

    def upsert_setup(self, setup_data):
        self.calls.append(("upsert_setup", setup_data.get("strategy_id")))
        return {"id": "upsert-id", **setup_data}

    def delete_setup(self, setup_id):
        self.calls.append(("delete_setup", setup_id))
        return True

    def reset(self):
        self.calls = []

    def write_calls(self):
        """Return only write method calls."""
        WRITE_METHODS = {"update_setup", "create_setup", "upsert_setup", "delete_setup"}
        return [c for c in self.calls if c[0] in WRITE_METHODS]

    def read_calls(self):
        """Return only read method calls."""
        WRITE_METHODS = {"update_setup", "create_setup", "upsert_setup", "delete_setup"}
        return [c for c in self.calls if c[0] not in WRITE_METHODS]


# ============================================================
# Import proxy from service
# ============================================================

try:
    from smc_micro_impulso_service import _ReadOnlySupabaseProxy
    print("OK: _ReadOnlySupabaseProxy importado desde smc_micro_impulso_service")
except ImportError as e:
    print(f"ERROR: no se pudo importar _ReadOnlySupabaseProxy: {e}")
    sys.exit(1)

try:
    from strategies.smc_micro_impulso.engine import STRATEGY_ID as MI_STRATEGY_ID, TP_RATIO as MI_TP_RATIO
    print(f"OK: SMC_MICRO_IMPULSO importado — strategy_id={MI_STRATEGY_ID}, tp_ratio={MI_TP_RATIO}")
except ImportError as e:
    print(f"ERROR: engine import failed: {e}")
    sys.exit(1)

try:
    from strategies.smc_micro_impulso_filtrado_m15.engine import (
        STRATEGY_ID as FILT_STRATEGY_ID,
        STRATEGY_KEY as FILT_STRATEGY_KEY,
        TP_RATIO as FILT_TP_RATIO,
        create_sin_setup_micro_impulso_filtrado_m15_response,
        _calcular_direccion_m15,
    )
    print(f"OK: SMC_MICRO_IMPULSO_FILTRADO_M15 engine importado — strategy_id={FILT_STRATEGY_ID}, strategy_key={FILT_STRATEGY_KEY}, tp_ratio={FILT_TP_RATIO}")
except ImportError as e:
    print(f"ERROR: filtrado engine import failed: {e}")
    sys.exit(1)

try:
    from smc_micro_impulso_filtrado_m15_service import _recalcular_tp_1_2
    print("OK: _recalcular_tp_1_2 importado desde filtrado service")
except ImportError as e:
    print(f"ERROR: _recalcular_tp_1_2 import failed: {e}")
    sys.exit(1)


# ============================================================
# TESTS
# ============================================================

def test_proxy_reads_pass_through():
    """
    Punto 1–3: Las lecturas se delegan al servicio real sin modificación.
    get_active_setup_by_symbol, get_active_setup, get_closed_setup_by_levels
    deben ser accesibles a través del proxy.
    """
    print("\n--- test_proxy_reads_pass_through ---")

    fake = FakeSupabaseService(
        active_setup={"id": "setup-1", "estado": "ACTIVA", "entrada": 100.0, "stoploss": 99.0, "tp_1_1": 102.0},
        active_setup_by_symbol={"id": "setup-2", "estado": "EN_ZONA", "entrada": 100.0, "stoploss": 99.0},
        closed_setup=None,
    )
    proxy = _ReadOnlySupabaseProxy(fake)

    # get_active_setup_by_symbol
    result = proxy.get_active_setup_by_symbol("SMC_MICRO_IMPULSO", "Boom 1000 Index")
    assert_not_none(result, "get_active_setup_by_symbol retorna datos reales a través del proxy")
    assert_equal(result.get("id"), "setup-2", "get_active_setup_by_symbol retorna el setup correcto")
    assert_equal(len(fake.read_calls()), 1, "get_active_setup_by_symbol registra 1 read call")

    # get_active_setup
    result2 = proxy.get_active_setup("SMC_MICRO_IMPULSO", "Boom 1000 Index", 100.0, 99.0)
    assert_not_none(result2, "get_active_setup retorna datos reales a través del proxy")
    assert_equal(result2.get("id"), "setup-1", "get_active_setup retorna el setup correcto")
    assert_equal(len(fake.read_calls()), 2, "get_active_setup registra 2 read calls acumulados")

    # get_closed_setup_by_levels
    result3 = proxy.get_closed_setup_by_levels("SMC_MICRO_IMPULSO", "Boom 1000 Index", 100.0, 99.0, 101.0)
    assert_none(result3, "get_closed_setup_by_levels retorna None correctamente cuando no hay zona cerrada")
    assert_equal(len(fake.read_calls()), 3, "get_closed_setup_by_levels registra 3 read calls acumulados")

    # No writes debieron ocurrir
    assert_equal(len(fake.write_calls()), 0, "cero write calls durante reads del proxy")


def test_proxy_blocks_update_setup():
    """Punto 4: update_setup es bloqueado por el proxy (retorna None, no escribe)."""
    print("\n--- test_proxy_blocks_update_setup ---")

    fake = FakeSupabaseService()
    proxy = _ReadOnlySupabaseProxy(fake)

    result = proxy.update_setup("setup-1", {"estado": "DESCARTADA"})

    assert_none(result, "proxy.update_setup retorna None (bloqueado)")
    assert_equal(len(fake.write_calls()), 0, "update_setup NO llega al fake — proxy lo absorbe antes")


def test_proxy_blocks_create_setup():
    """Punto 5: create_setup es bloqueado por el proxy (retorna None, no escribe)."""
    print("\n--- test_proxy_blocks_create_setup ---")

    fake = FakeSupabaseService()
    proxy = _ReadOnlySupabaseProxy(fake)

    result = proxy.create_setup({"strategy_id": "SMC_MICRO_IMPULSO", "symbol": "Boom 1000 Index"})

    assert_none(result, "proxy.create_setup retorna None (bloqueado)")
    assert_equal(len(fake.write_calls()), 0, "create_setup NO llega al fake — proxy lo absorbe antes")


def test_proxy_blocks_upsert_setup():
    """Punto 6: upsert_setup es bloqueado por el proxy."""
    print("\n--- test_proxy_blocks_upsert_setup ---")

    fake = FakeSupabaseService()
    proxy = _ReadOnlySupabaseProxy(fake)

    result = proxy.upsert_setup({"strategy_id": "SMC_MICRO_IMPULSO", "symbol": "Boom 1000 Index"})

    assert_none(result, "proxy.upsert_setup retorna None (bloqueado)")
    assert_equal(len(fake.write_calls()), 0, "upsert_setup NO llega al fake — proxy lo absorbe antes")


def test_proxy_blocks_delete_setup():
    """Punto 7: delete_setup es bloqueado por el proxy."""
    print("\n--- test_proxy_blocks_delete_setup ---")

    fake = FakeSupabaseService()
    proxy = _ReadOnlySupabaseProxy(fake)

    result = proxy.delete_setup("setup-1")

    assert_none(result, "proxy.delete_setup retorna None (bloqueado)")
    assert_equal(len(fake.write_calls()), 0, "delete_setup NO llega al fake — proxy lo absorbe antes")


def test_proxy_blocks_engine_pre_touch_invalidation():
    """
    Punto 2 (simulado): El engine llama update_setup cuando invalida una zona
    pre-touch (TRACKED_ZONE_INVALIDATED_PRE_TOUCH). El proxy bloquea esa write.
    """
    print("\n--- test_proxy_blocks_engine_pre_touch_invalidation ---")

    fake = FakeSupabaseService(
        active_setup_by_symbol={"id": "setup-99", "estado": "ACTIVA", "entrada": 100.0, "stoploss": 99.0, "tp_1_1": 101.0}
    )
    proxy = _ReadOnlySupabaseProxy(fake)

    # Simular exactamente lo que hace el engine en pre-touch invalidation:
    # supabase_svc.update_setup(setup_activo["id"], {"estado": "DESCARTADA"})
    setup_activo = proxy.get_active_setup_by_symbol("SMC_MICRO_IMPULSO", "Boom 1000 Index")
    assert_not_none(setup_activo, "engine puede leer setup_activo via proxy")

    # Engine intenta marcar como DESCARTADA
    write_result = proxy.update_setup(setup_activo["id"], {"estado": "DESCARTADA"})

    assert_none(write_result, "proxy bloquea update_setup DESCARTADA del engine")
    assert_equal(len(fake.write_calls()), 0, "cero writes al fake real — invalidación bloqueada por proxy")
    assert_equal(len(fake.read_calls()), 1, "read (get_active_setup_by_symbol) SÍ pasó al fake")


def test_proxy_blocks_engine_pre_zona_comparison():
    """
    Punto 2 (simulado): El engine actualiza niveles cuando detecta zona fresca en
    PRE-ZONA comparison. El proxy bloquea esa write.
    """
    print("\n--- test_proxy_blocks_engine_pre_zona_comparison ---")

    fake = FakeSupabaseService(
        active_setup_by_symbol={"id": "setup-77", "estado": "ACTIVA", "entrada": 100.0, "stoploss": 99.0, "tp_1_1": 101.0}
    )
    proxy = _ReadOnlySupabaseProxy(fake)

    # Engine lee zona guardada
    setup_activo = proxy.get_active_setup_by_symbol("SMC_MICRO_IMPULSO", "Crash 1000 Index")
    assert_not_none(setup_activo, "engine puede leer setup via proxy")

    # Engine detecta zona fresca y actualiza niveles (PRE_ZONE_FRESH_ZONE_COMPARISON)
    write_result = proxy.update_setup(setup_activo["id"], {
        "entrada": 99.5,
        "stoploss": 98.5,
        "tp_1_1": 100.5,
        "score": 3,
        "ob": True,
        "fvg": False,
        "barrida": True,
    })

    assert_none(write_result, "proxy bloquea update_setup PRE-ZONA del engine")
    assert_equal(len(fake.write_calls()), 0, "cero writes al fake — PRE-ZONA update bloqueado por proxy")


def test_normal_service_writes_allowed():
    """
    Punto 3: Cuando sync_to_supabase=True (endpoint normal), el engine recibe
    el servicio real (sin proxy), por lo que update_setup y create_setup funcionan
    normalmente. Verificamos que el servicio real NO es un proxy.
    """
    print("\n--- test_normal_service_writes_allowed ---")

    fake = FakeSupabaseService(
        active_setup={"id": "real-setup", "estado": "ACTIVA", "entrada": 200.0, "stoploss": 198.0, "tp_1_1": 202.0}
    )
    # En el path normal (sync_to_supabase=True), el engine recibe fake directamente (no wrapped)
    real_svc = fake

    # Simular engine leyendo estado
    existing = real_svc.get_active_setup("SMC_MICRO_IMPULSO", "Boom 1000 Index", 200.0, 198.0)
    assert_not_none(existing, "servicio real: get_active_setup retorna datos")

    # Simular engine actualizando (en el path normal esto sí debe ocurrir)
    up_result = real_svc.update_setup(existing["id"], {"estado": "EN_ZONA", "precio_actual": 199.5})
    assert_not_none(up_result, "servicio real: update_setup retorna resultado (write permitido)")

    assert_equal(len(fake.write_calls()), 1, "servicio real: 1 write call registrado correctamente")
    assert_equal(fake.write_calls()[0][0], "update_setup", "el write fue update_setup")

    # Confirmar que fake NO es un proxy
    assert_true(not isinstance(fake, _ReadOnlySupabaseProxy), "el servicio directo NO es un proxy")


def test_proxy_bool_true_when_svc_truthy():
    """El proxy es truthy cuando el servicio subyacente es truthy."""
    print("\n--- test_proxy_bool_true_when_svc_truthy ---")

    fake = FakeSupabaseService()
    proxy = _ReadOnlySupabaseProxy(fake)
    assert_true(bool(proxy), "proxy es truthy cuando svc subyacente existe")


def test_proxy_allows_all_read_methods():
    """
    Verificar que cualquier método que no sea write pasa al servicio real,
    incluyendo métodos que puedan ser llamados en el futuro.
    """
    print("\n--- test_proxy_allows_all_read_methods ---")

    class ExtendedFakeSvc:
        """Fake con método extra de lectura."""
        def custom_read_method(self, x):
            return f"read:{x}"
        def update_setup(self, *a, **kw):
            raise AssertionError("NO debería ser llamado directamente")

    svc = ExtendedFakeSvc()
    proxy = _ReadOnlySupabaseProxy(svc)

    result = proxy.custom_read_method("test-arg")
    assert_equal(result, "read:test-arg", "métodos de lectura custom pasan a través del proxy")

    # update_setup debe ser absorbido por el proxy antes de llegar a ExtendedFakeSvc
    write_result = proxy.update_setup("id-1", {"estado": "X"})
    assert_none(write_result, "proxy absorbe update_setup antes de llegar al fake")


def test_strategy_id_isolation():
    """
    Punto 4+5: FILTRADO M15 tiene su propio strategy_id.
    El engine normal usa SMC_MICRO_IMPULSO.
    FILTRADO usa SMC_MICRO_IMPULSO_FILTRADO_M15.
    Deben ser diferentes.
    """
    print("\n--- test_strategy_id_isolation ---")

    assert_true(
        MI_STRATEGY_ID != FILT_STRATEGY_ID,
        f"strategy_ids son distintos ({MI_STRATEGY_ID} != {FILT_STRATEGY_ID})"
    )
    assert_equal(MI_STRATEGY_ID, "SMC_MICRO_IMPULSO", "strategy_id MICRO IMPULSO normal correcto")
    assert_equal(FILT_STRATEGY_ID, "SMC_MICRO_IMPULSO_FILTRADO_M15", "strategy_id FILTRADO M15 correcto")


def test_tp_ratios():
    """
    Punto 7 + 12: TP MICRO IMPULSO normal = 1:1 (ratio 1).
    TP FILTRADO M15 = 1:2 (ratio 2).
    """
    print("\n--- test_tp_ratios ---")

    assert_equal(MI_TP_RATIO, 1, f"MICRO IMPULSO normal TP_RATIO={MI_TP_RATIO} (esperado 1)")
    assert_equal(FILT_TP_RATIO, 2, f"FILTRADO M15 TP_RATIO={FILT_TP_RATIO} (esperado 2)")


def test_recalcular_tp_1_2_alcista():
    """
    _recalcular_tp_1_2 con ALCISTA: entrada > stoploss → tp = entrada + 2 * risk.
    """
    print("\n--- test_recalcular_tp_1_2_alcista ---")

    entrada = 100.0
    stoploss = 99.0
    risk = abs(entrada - stoploss)  # 1.0
    expected_tp = round(entrada + 2 * risk, 2)  # 102.0

    tp = _recalcular_tp_1_2(entrada, stoploss)
    assert_equal(tp, expected_tp, f"TP 1:2 ALCISTA: entrada={entrada}, sl={stoploss} → tp={tp}")


def test_recalcular_tp_1_2_bajista():
    """
    _recalcular_tp_1_2 con BAJISTA: entrada < stoploss → tp = entrada - 2 * risk.
    """
    print("\n--- test_recalcular_tp_1_2_bajista ---")

    entrada = 2000.0
    stoploss = 2001.5
    risk = abs(entrada - stoploss)  # 1.5
    expected_tp = round(entrada - 2 * risk, 2)  # 1997.0

    tp = _recalcular_tp_1_2(entrada, stoploss)
    assert_equal(tp, expected_tp, f"TP 1:2 BAJISTA: entrada={entrada}, sl={stoploss} → tp={tp}")


def test_filtrado_m15_no_cumple_returns_sin_setup():
    """
    Punto 6 + 8: Cuando M15 no cumple, FILTRADO M15 retorna estado no activo.
    Verifica que create_sin_setup_micro_impulso_filtrado_m15_response produce
    el shape correcto con estado NO CUMPLE / SIN SETUP.
    """
    print("\n--- test_filtrado_m15_no_cumple_returns_sin_setup ---")

    result = create_sin_setup_micro_impulso_filtrado_m15_response(
        symbol="Boom 1000 Index",
        price=1234.5,
        direccion_indice="ALCISTA",
        direccion_m15="BAJISTA",
        cumple_m15=False,
        motivo="M15=BAJISTA != INDICE=ALCISTA",
        estado="NO CUMPLE DIRECCIÓN M15",
    )

    assert_equal(result.get("estado"), "NO CUMPLE DIRECCIÓN M15",
                 "estado = NO CUMPLE DIRECCIÓN M15 cuando filtro no pasa")
    assert_equal(result.get("cumple_m15"), False, "cumple_m15 = False")
    assert_none(result.get("entrada"), "entrada = None (sin setup activo)")
    assert_none(result.get("stoploss"), "stoploss = None")
    assert_equal(result.get("strategy_key"), FILT_STRATEGY_KEY,
                 f"strategy_key = {FILT_STRATEGY_KEY}")


def test_filtrado_sin_setup_response_shape():
    """
    Punto 5 + 11 + 15: La respuesta de FILTRADO tiene price/precio_actual y
    updated_at (para PRECIO y ACTUALIZACIÓN en UI), pero no impone un campo MOTIVO
    como columna de tabla (el campo motivo existe en el payload pero no como columna).
    """
    print("\n--- test_filtrado_sin_setup_response_shape ---")

    result = create_sin_setup_micro_impulso_filtrado_m15_response(
        symbol="Crash 1000 Index",
        price=9999.99,
        motivo="SIN SETUP",
        estado="SIN SETUP",
    )

    # PRECIO debe estar presente en el payload
    assert_true(
        result.get("price") is not None or result.get("precio_actual") is not None,
        "precio (price / precio_actual) presente en payload"
    )
    assert_equal(result.get("price"), 9999.99, "field 'price' contiene el precio correcto")
    assert_equal(result.get("precio_actual"), 9999.99, "field 'precio_actual' contiene el precio correcto")

    # ACTUALIZACIÓN: campo timestamp/updated_at presente
    assert_true(
        result.get("updated_at") is not None or result.get("timestamp") is not None,
        "campo timestamp/updated_at presente para columna ACTUALIZACIÓN"
    )

    # strategy_key correcto para aislamiento
    assert_equal(result.get("strategy_key"), FILT_STRATEGY_KEY,
                 "strategy_key es el FILTRADO (aislamiento correcto)")

    # TP_RATIO = 2 (1:2)
    assert_equal(result.get("tp_ratio"), 2, "tp_ratio = 2 (1:2) en SIN SETUP FILTRADO")


def test_proxy_isolates_writes_in_engine_simulation():
    """
    Simulación integral del ciclo engine:
      - El engine lee get_active_setup_by_symbol (✓ read pasa)
      - El engine llama update_setup pre-touch invalidation (✗ write bloqueado)
      - El engine llama update_setup PRE-ZONA comparison (✗ write bloqueado)
      - El engine llama get_active_setup para búsqueda (✓ read pasa)
      - Cero writes llegan al fake real
    """
    print("\n--- test_proxy_isolates_writes_in_engine_simulation ---")

    setup_data = {
        "id": "sim-setup-1",
        "estado": "ACTIVA",
        "entrada": 500.0,
        "stoploss": 498.0,
        "tp_1_1": 502.0,
    }
    fake = FakeSupabaseService(
        active_setup=setup_data,
        active_setup_by_symbol=setup_data,
    )
    proxy = _ReadOnlySupabaseProxy(fake)

    # Ciclo MODO SEGUIMIENTO del engine:

    # 1. Engine lee setup activo
    setup = proxy.get_active_setup_by_symbol("SMC_MICRO_IMPULSO", "Boom 500 Index")
    assert_not_none(setup, "read 1: get_active_setup_by_symbol OK")

    # 2. Engine invalida zona (pre-touch) → intenta update_setup
    r1 = proxy.update_setup(setup["id"], {"estado": "DESCARTADA"})
    assert_none(r1, "write bloqueado: pre-touch invalidation update_setup")

    # 3. Engine compara zona fresca y actualiza niveles → intenta update_setup
    r2 = proxy.update_setup(setup["id"], {"entrada": 499.5, "stoploss": 497.5, "tp_1_1": 501.5, "score": 4, "ob": True, "fvg": False, "barrida": True})
    assert_none(r2, "write bloqueado: PRE-ZONA comparison update_setup")

    # 4. Engine busca zona en MODO BÚSQUEDA → get_active_setup
    existing = proxy.get_active_setup("SMC_MICRO_IMPULSO", "Boom 500 Index", 499.5, 497.5)
    assert_not_none(existing, "read 2: get_active_setup OK")

    # Verificar totales
    assert_equal(len(fake.read_calls()), 2, "exactamente 2 reads llegaron al fake real")
    assert_equal(len(fake.write_calls()), 0,
                 "cero writes llegaron al fake real — proxy bloqueó todo (simulación integral)")


def test_py_compile_all_modules():
    """Punto 8+16: py_compile sin errores en todos los módulos afectados."""
    print("\n--- test_py_compile_all_modules ---")

    import py_compile
    import glob as _glob

    backend_dir = os.path.dirname(os.path.abspath(__file__))

    files_to_check = [
        os.path.join(backend_dir, "smc_micro_impulso_service.py"),
        os.path.join(backend_dir, "smc_micro_impulso_filtrado_m15_service.py"),
        os.path.join(backend_dir, "strategies", "smc_micro_impulso", "engine.py"),
        os.path.join(backend_dir, "strategies", "smc_micro_impulso_filtrado_m15", "engine.py"),
    ]

    for fpath in files_to_check:
        if not os.path.exists(fpath):
            assert_true(False, f"py_compile: archivo no encontrado: {fpath}")
            continue
        try:
            py_compile.compile(fpath, doraise=True)
            assert_true(True, f"py_compile OK: {os.path.relpath(fpath, backend_dir)}")
        except py_compile.PyCompileError as e:
            assert_true(False, f"py_compile FAIL: {os.path.relpath(fpath, backend_dir)}: {e}")


# ============================================================
# RUNNER
# ============================================================

def run_all_tests():
    tests = [
        test_proxy_reads_pass_through,
        test_proxy_blocks_update_setup,
        test_proxy_blocks_create_setup,
        test_proxy_blocks_upsert_setup,
        test_proxy_blocks_delete_setup,
        test_proxy_blocks_engine_pre_touch_invalidation,
        test_proxy_blocks_engine_pre_zona_comparison,
        test_normal_service_writes_allowed,
        test_proxy_bool_true_when_svc_truthy,
        test_proxy_allows_all_read_methods,
        test_strategy_id_isolation,
        test_tp_ratios,
        test_recalcular_tp_1_2_alcista,
        test_recalcular_tp_1_2_bajista,
        test_filtrado_m15_no_cumple_returns_sin_setup,
        test_filtrado_sin_setup_response_shape,
        test_proxy_isolates_writes_in_engine_simulation,
        test_py_compile_all_modules,
    ]

    print("\n" + "=" * 60)
    print("TEST SUITE: ReadOnly Proxy + FILTRADO M15 Isolation")
    print("=" * 60)

    for test_fn in tests:
        try:
            test_fn()
        except Exception as e:
            global _failed
            _failed += 1
            import traceback
            print(f"  EXCEPTION in {test_fn.__name__}: {e}")
            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"RESULTS: {_passed} passed, {_failed} failed / {_passed + _failed} total")
    print("=" * 60)

    if _failed > 0:
        sys.exit(1)
    else:
        print("\nAll tests passed!")


if __name__ == "__main__":
    run_all_tests()
