#!/usr/bin/env python3
"""
Test script to verify API endpoints structure
"""

import sys
sys.path.insert(0, '../../')

# Test imports
try:
    from smc_m15_service import analyze_symbol_smc, create_sin_setup_response
    print("✅ SMC service imported")
except ImportError as e:
    print(f"❌ SMC service import failed: {e}")
    sys.exit(1)

# Test create_sin_setup_response
result = create_sin_setup_response("Boom 1000 Index", 12345.67)
print(f"✅ SIN SETUP response created: {result['symbol']}")

# Verify structure
expected_keys = [
    'symbol', 'price', 'tendencia_h1', 'tendencia_m15', 
    'ultimo_evento_m15', 'zona_madre_m15', 'score', 
    'ob', 'fvg', 'barrida', 'estado', 'updated_at'
]

for key in expected_keys:
    if key not in result:
        print(f"❌ Missing key: {key}")
        sys.exit(1)

print(f"✅ All expected keys present")
print(f"✅ Response structure:")
print(f"   - Symbol: {result['symbol']}")
print(f"   - Price: {result['price']}")
print(f"   - Estado: {result['estado']}")
print(f"   - Score: {result['score']}")
print(f"   - Tendencia H1: {result['tendencia_h1']}")
print(f"   - Tendencia M15: {result['tendencia_m15']}")

print("\n✅ All tests passed!")
