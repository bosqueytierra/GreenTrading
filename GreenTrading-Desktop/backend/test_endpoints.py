#!/usr/bin/env python3
"""
Test script to verify API endpoints structure
"""

import sys
sys.path.insert(0, '../../')

# Test imports
try:
    from smc_m15_service import analyze_symbol_smc, create_sin_setup_response
    print("OK: SMC service imported")
except ImportError as e:
    print(f"ERROR: SMC service import failed: {e}")
    sys.exit(1)

# Test create_sin_setup_response
result = create_sin_setup_response("Boom 1000 Index", 12345.67)
print(f"OK: SIN SETUP response created: {result['symbol']}")

# Verify structure
expected_keys = [
    'symbol', 'price', 'tendencia_h1', 'tendencia_m15', 
    'ultimo_evento_m15', 'zona_madre_m15', 'entrada', 'stoploss', 'tp_1_1', 'score', 
    'ob', 'fvg', 'barrida', 'estado', 'updated_at'
]

for key in expected_keys:
    if key not in result:
        print(f"ERROR: Missing key: {key}")
        sys.exit(1)

print(f"OK: All expected keys present")
print(f"OK: Response structure:")
print(f"   - Symbol: {result['symbol']}")
print(f"   - Price: {result['price']}")
print(f"   - Estado: {result['estado']}")
print(f"   - Score: {result['score']}")
print(f"   - Tendencia H1: {result['tendencia_h1']}")
print(f"   - Tendencia M15: {result['tendencia_m15']}")
print(f"   - Entrada: {result['entrada']}")
print(f"   - StopLoss: {result['stoploss']}")

if result['entrada'] is not None or result['stoploss'] is not None:
    print("ERROR: SIN SETUP response should expose entrada/stoploss as None")
    sys.exit(1)

print("\nOK: All tests passed!")
