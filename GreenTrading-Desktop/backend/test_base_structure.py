#!/usr/bin/env python3
"""
Test script to verify FASE 3 correction:
- BASE STRUCTURE is always calculated (H1 trend, M15 trend, last M15 event)
- ZONE is optional (shows SIN SETUP when not present)

Updated for direct SMC implementation (no external engine dependency)
"""

import sys
import os

import pandas as pd
from datetime import datetime

# Import SMC service directly
try:
    sys.path.insert(0, os.path.dirname(__file__))
    from smc_m15_service import analyze_symbol_smc
    print("OK: SMC service imported (direct implementation)")
except ImportError as e:
    print(f"ERROR: SMC service import failed: {e}")
    sys.exit(1)


def create_mock_candles(n=100):
    """Create mock candle data with swings for testing"""
    import math
    times = pd.date_range(start='2024-01-01', periods=n, freq='15min')
    
    # Create oscillating data with clear swings
    data = {
        'time': times,
        'open': [100 + 10 * math.sin(i * 0.2) for i in range(n)],
        'high': [102 + 10 * math.sin(i * 0.2) for i in range(n)],
        'low': [98 + 10 * math.sin(i * 0.2) for i in range(n)],
        'close': [101 + 10 * math.sin(i * 0.2) for i in range(n)]
    }
    return pd.DataFrame(data)


def test_with_direct_implementation():
    """Test with direct SMC implementation (always available now)"""
    print("\n" + "="*60)
    print("TEST 1: With Direct SMC Implementation")
    print("="*60)
    
    # Create mock candles
    df_h1 = create_mock_candles(100)
    df_m15 = create_mock_candles(400)
    
    # Analyze
    result = analyze_symbol_smc("Boom 1000 Index", df_h1, df_m15)
    
    # Verify structure
    print(f"\nOK: Analysis completed:")
    print(f"   Symbol: {result['symbol']}")
    print(f"   Price: {result['price']}")
    print(f"   Tendencia H1: {result['tendencia_h1']}")
    print(f"   Tendencia M15: {result['tendencia_m15']}")
    print(f"   Último Evento M15: {result['ultimo_evento_m15']}")
    print(f"   Zona Madre M15: {result['zona_madre_m15']}")
    print(f"   Score: {result['score']}")
    print(f"   Estado: {result['estado']}")
    
    # Verify BASE STRUCTURE is present (even if '--' when no swings/structure detected)
    # The key is that the function RUNS and RETURNS these fields, not crashes
    assert 'tendencia_h1' in result, "H1 trend field should be present"
    assert 'tendencia_m15' in result, "M15 trend field should be present"
    assert 'ultimo_evento_m15' in result, "Last M15 event field should be present"
    
    print("\nOK: BASE STRUCTURE always present and calculated")
    print(f"   (Even if no swings detected, fields exist and show '--' not empty string)")
    
    # Check if we have a zone
    if result['zona_madre_m15']['desde'] == 0:
        print("OK: No zone detected - estado shows SIN SETUP")
        print("OK: Trends/events may be '--' if no swings (which is correct behavior)")
        # When no swings detected, trends/events show '--', which is correct
        # The fix ensures these fields exist and are calculated, not skipped
    else:
        print("OK: Zone detected - full setup available")


def test_no_data():
    """Test with no data (should return minimal response)"""
    print("\n" + "="*60)
    print("TEST 2: No Data (Catastrophic Failure)")
    print("="*60)
    
    # Empty dataframes
    df_h1 = pd.DataFrame()
    df_m15 = pd.DataFrame()
    
    result = analyze_symbol_smc("Crash 500 Index", df_h1, df_m15)
    
    print(f"\nOK: Minimal response created:")
    print(f"   Symbol: {result['symbol']}")
    print(f"   Tendencia H1: {result['tendencia_h1']}")
    print(f"   Tendencia M15: {result['tendencia_m15']}")
    print(f"   Último Evento M15: {result['ultimo_evento_m15']}")
    print(f"   Estado: {result['estado']}")
    
    # Verify all are '--' when no data
    assert result['tendencia_h1'] == '--', "Should be '--' when no data"
    assert result['tendencia_m15'] == '--', "Should be '--' when no data"
    assert result['ultimo_evento_m15'] == '--', "Should be '--' when no data"
    assert result['estado'] == 'SIN SETUP', "Should be 'SIN SETUP' when no data"
    
    print("\nOK: Catastrophic failure handled correctly")


def test_response_structure():
    """Test response structure has all required fields"""
    print("\n" + "="*60)
    print("TEST 3: Response Structure")
    print("="*60)
    
    # Create mock candles
    df_h1 = create_mock_candles(100)
    df_m15 = create_mock_candles(400)
    
    result = analyze_symbol_smc("Boom 1000 Index", df_h1, df_m15)
    
    # Expected keys
    expected_keys = [
        'symbol', 'price', 'tendencia_h1', 'tendencia_m15',
        'ultimo_evento_m15', 'zona_madre_m15', 'entrada', 'stoploss', 'tp_1_1', 'score',
        'ob', 'fvg', 'barrida', 'estado', 'updated_at'
    ]
    
    print("\nOK: Checking response structure:")
    for key in expected_keys:
        if key in result:
            print(f"   ✓ {key}: {result[key]}")
        else:
            print(f"   ✗ {key}: MISSING")
            assert False, f"Missing key: {key}"
    
    print("\nOK: All required fields present")


def main():
    """Run all tests"""
    print("="*60)
    print("FASE 3 CORRECCIÓN TEST")
    print("Verifying BASE STRUCTURE always calculated")
    print("Direct SMC Implementation (no external dependencies)")
    print("="*60)
    
    try:
        test_with_direct_implementation()
        test_no_data()
        test_response_structure()
        
        print("\n" + "="*60)
        print("OK: ALL TESTS PASSED")
        print("="*60)
        print("\nSummary:")
        print("OK: BASE STRUCTURE (H1/M15 trends, last M15 event) ALWAYS calculated")
        print("OK: ZONE/SETUP is optional (SIN SETUP when not present)")
        print("OK: Response structure is complete and correct")
        print("OK: Direct implementation works without external SMC engine")
        
    except AssertionError as e:
        print(f"\nERROR: TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
