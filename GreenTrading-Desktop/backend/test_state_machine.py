#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test State Machine Validation
Verifica que las transiciones de estado sean correctas
"""

import sys
sys.path.insert(0, '/home/runner/work/GreenTrading/GreenTrading/GreenTrading-Desktop/backend')

from smc_m15_service import calcular_transicion_estado

def test_case(name, symbol, estado_previo, estado_calculado, precio_actual, entrada, stoploss, tp, zona_desde, zona_hasta, expected_estado, expected_motivo_keyword):
    """Ejecuta un test case y muestra resultado"""
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")
    print(f"  Estado previo: {estado_previo}")
    print(f"  Estado calculado: {estado_calculado}")
    print(f"  Precio actual: {precio_actual}")
    print(f"  Entrada: {entrada}, SL: {stoploss}, TP: {tp}")
    print(f"  Zona: {zona_desde} - {zona_hasta}")
    
    estado_final, motivo = calcular_transicion_estado(
        symbol,
        estado_previo,
        estado_calculado,
        precio_actual,
        entrada,
        stoploss,
        tp,
        zona_desde,
        zona_hasta
    )
    
    print(f"\n  RESULTADO:")
    print(f"    Estado final: {estado_final}")
    print(f"    Motivo: {motivo}")
    
    # Verificar resultado
    if estado_final == expected_estado and expected_motivo_keyword in motivo:
        print(f"  ✓ PASS - Estado: {estado_final}, Motivo contiene '{expected_motivo_keyword}'")
        return True
    else:
        print(f"  ✗ FAIL")
        print(f"    Esperado: {expected_estado} con motivo que contenga '{expected_motivo_keyword}'")
        print(f"    Obtenido: {estado_final} con motivo '{motivo}'")
        return False

def main():
    print("\n" + "="*80)
    print("TESTING STATE MACHINE - REGLAS DE TRANSICION")
    print("="*80)
    
    tests_passed = 0
    tests_total = 0
    
    # Test 1: Nueva zona detectada lejos de precio - debe quedar ESPERANDO_ENTRADA
    tests_total += 1
    # Test 1: Nueva zona detectada lejos de precio - debe quedar ESPERANDO_ENTRADA  
    tests_total += 1
    if test_case(
        "Nueva zona lejos del precio",
        "Boom 1000 Index",
        None,  # Sin estado previo (nueva zona)
        "ESPERANDO_ENTRADA",
        1025.0,  # Precio actual (arriba de SL, debajo de zona)
        1050.0,  # Entrada (arriba - Boom ALCISTA)
        1020.0,  # SL (abajo)
        1070.0,  # TP (arriba)
        1040.0,  # Zona desde
        1050.0,  # Zona hasta
        "ESPERANDO_ENTRADA",
        "Nueva zona"
    ):
        tests_passed += 1
    
    # Test 2: Nueva zona pero precio ya está EN_ZONA - debe quedar ACTIVA (no EN_ZONA sin historial)
    tests_total += 1
    if test_case(
        "Nueva zona con precio EN_ZONA (no permitido sin historial)",
        "Boom 1000 Index",
        None,  # Sin estado previo
        "EN_ZONA",  # El cálculo dice EN_ZONA
        1045.0,  # Precio dentro de zona
        1050.0,
        1040.0,
        1060.0,
        1040.0,
        1050.0,
        "ACTIVA",  # Debe corregir a ACTIVA
        "sin historial previo"
    ):
        tests_passed += 1
    
    # Test 3: Nueva zona pero precio ya está en PROFIT - debe quedar ACTIVA (no PROFIT sin historial)
    tests_total += 1
    if test_case(
        "Nueva zona con precio en PROFIT (no permitido sin historial)",
        "Boom 1000 Index",
        None,
        "PROFIT",
        1055.0,  # Precio arriba de entrada
        1050.0,
        1040.0,
        1060.0,
        1040.0,
        1050.0,
        "ACTIVA",
        "sin historial previo"
    ):
        tests_passed += 1
    
    # Test 4: Transición válida ACTIVA → EN_ZONA
    tests_total += 1
    if test_case(
        "Transición válida ACTIVA a EN_ZONA",
        "Boom 1000 Index",
        "ACTIVA",  # Estado previo
        "EN_ZONA",
        1045.0,  # Precio en zona
        1050.0,
        1040.0,
        1060.0,
        1040.0,
        1050.0,
        "EN_ZONA",
        "tocó la zona"
    ):
        tests_passed += 1
    
    # Test 5: Transición inválida ACTIVA → PROFIT (debe mantener ACTIVA)
    tests_total += 1
    if test_case(
        "Transición inválida ACTIVA a PROFIT (sin pasar por EN_ZONA)",
        "Boom 1000 Index",
        "ACTIVA",
        "PROFIT",  # El cálculo dice PROFIT
        1055.0,  # Precio arriba
        1050.0,
        1040.0,
        1060.0,
        1040.0,
        1050.0,
        "ACTIVA",  # Debe mantener ACTIVA
        "sin pasar por EN_ZONA"
    ):
        tests_passed += 1
    
    # Test 6: Transición válida EN_ZONA → PROFIT
    tests_total += 1
    if test_case(
        "Transición válida EN_ZONA a PROFIT",
        "Boom 1000 Index",
        "EN_ZONA",
        "PROFIT",
        1055.0,  # Precio arriba de entrada
        1050.0,
        1040.0,
        1060.0,
        1040.0,
        1050.0,
        "PROFIT",
        "dirección favorable"
    ):
        tests_passed += 1
    
    # Test 7: Transición válida EN_ZONA → TP
    tests_total += 1
    if test_case(
        "Transición válida EN_ZONA a TP",
        "Boom 1000 Index",
        "EN_ZONA",
        "TP",
        1061.0,  # Precio alcanzó TP
        1050.0,
        1040.0,
        1060.0,
        1040.0,
        1050.0,
        "TP",
        "Take Profit"
    ):
        tests_passed += 1
    
    # Test 8: Nueva zona en TP - no debe permitir TP sin historial
    tests_total += 1
    if test_case(
        "Nueva zona en TP (no permitido sin historial)",
        "Boom 1000 Index",
        None,
        "TP",
        1061.0,
        1050.0,
        1040.0,
        1060.0,
        1040.0,
        1050.0,
        "ACTIVA",
        "Nueva zona"
    ):
        tests_passed += 1
    
    # Test 9: Transición válida ACTIVA → SL
    tests_total += 1
    if test_case(
        "Transición válida ACTIVA a SL",
        "Boom 1000 Index",
        "ACTIVA",
        "SL",
        1039.0,  # Precio tocó SL (abajo)
        1050.0,
        1040.0,
        1060.0,
        1040.0,
        1050.0,
        "SL",
        "Stop Loss"
    ):
        tests_passed += 1
    
    # Test 10: Estado terminal TP no cambia
    tests_total += 1
    if test_case(
        "Estado terminal TP no cambia",
        "Boom 1000 Index",
        "TP",
        "PROFIT",  # Aunque calcule PROFIT
        1055.0,
        1050.0,
        1040.0,
        1060.0,
        1040.0,
        1050.0,
        "TP",  # Debe mantener TP
        "terminal"
    ):
        tests_passed += 1
    
    # RESUMEN
    print("\n" + "="*80)
    print(f"RESUMEN DE TESTS")
    print("="*80)
    print(f"Tests pasados: {tests_passed}/{tests_total}")
    print(f"Tests fallidos: {tests_total - tests_passed}")
    
    if tests_passed == tests_total:
        print("\n✓ TODOS LOS TESTS PASARON")
        return 0
    else:
        print(f"\n✗ {tests_total - tests_passed} TESTS FALLARON")
        return 1

if __name__ == "__main__":
    sys.exit(main())
