#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for SMC M15 Service
Validates the direct implementation logic
"""

import sys
import pandas as pd
from datetime import datetime, timedelta

# Import the service
from smc_m15_service import (
    detectar_swings,
    detectar_estructura,
    detectar_fvg,
    buscar_order_block,
    detectar_barrida_previa,
    crear_zona_m15,
    direccion_operativa_por_indice,
    validar_zona_operativa,
    analyze_symbol_smc
)

def create_sample_data(num_candles=100, trend="ALCISTA"):
    """Create sample candle data for testing"""
    base_price = 1000.0
    dates = [datetime.now() - timedelta(minutes=i*15) for i in range(num_candles, 0, -1)]
    
    data = {
        'time': dates,
        'open': [],
        'high': [],
        'low': [],
        'close': []
    }
    
    # Create a trending pattern
    for i in range(num_candles):
        if trend == "ALCISTA":
            open_price = base_price + i * 0.5
            close_price = open_price + (1 if i % 3 == 0 else 0.3)
        else:
            open_price = base_price - i * 0.5
            close_price = open_price - (1 if i % 3 == 0 else 0.3)
        
        high_price = max(open_price, close_price) + 0.2
        low_price = min(open_price, close_price) - 0.2
        
        data['open'].append(open_price)
        data['high'].append(high_price)
        data['low'].append(low_price)
        data['close'].append(close_price)
    
    return pd.DataFrame(data)

def test_swings():
    """Test swing detection"""
    print("\n" + "="*60)
    print("TEST 1: Swing Detection")
    print("="*60)
    
    df = create_sample_data(50, "ALCISTA")
    swings = detectar_swings(df, lookback=3)
    
    print(f"✓ DataFrame size: {len(df)}")
    print(f"✓ Swings detected: {len(swings)}")
    
    if len(swings) > 0:
        print(f"  - First swing: {swings[0]['tipo']} at price {swings[0]['precio']:.2f}")
        print(f"  - Last swing: {swings[-1]['tipo']} at price {swings[-1]['precio']:.2f}")
        print("✅ PASSED")
    else:
        print("⚠️  No swings detected (might be normal for small/flat data)")
    
    return swings

def test_estructura(swings):
    """Test structure detection"""
    print("\n" + "="*60)
    print("TEST 2: Structure Detection")
    print("="*60)
    
    df = create_sample_data(50, "ALCISTA")
    eventos, tendencia = detectar_estructura(df, swings)
    
    print(f"✓ Events detected: {len(eventos)}")
    print(f"✓ Current trend: {tendencia}")
    
    if len(eventos) > 0:
        print(f"  - First event: {eventos[0]['evento']} at {eventos[0]['precio_cierre']:.2f}")
        print(f"  - Last event: {eventos[-1]['evento']} at {eventos[-1]['precio_cierre']:.2f}")
        print("✅ PASSED")
    else:
        print("⚠️  No events detected")
    
    return eventos, tendencia

def test_fvg():
    """Test FVG detection"""
    print("\n" + "="*60)
    print("TEST 3: FVG Detection")
    print("="*60)
    
    df = create_sample_data(50, "ALCISTA")
    fvgs = detectar_fvg(df)
    
    print(f"✓ FVGs detected: {len(fvgs)}")
    
    if len(fvgs) > 0:
        print(f"  - First FVG: {fvgs[0]['tipo']} from {fvgs[0]['desde']:.2f} to {fvgs[0]['hasta']:.2f}")
        print("✅ PASSED")
    else:
        print("⚠️  No FVGs detected (normal for smooth trends)")
    
    return fvgs

def test_full_analysis():
    """Test full symbol analysis"""
    print("\n" + "="*60)
    print("TEST 4: Full Symbol Analysis")
    print("="*60)
    
    # Test with Boom symbol
    symbol = "Boom 1000 Index"
    df_h1 = create_sample_data(100, "ALCISTA")
    df_m15 = create_sample_data(100, "ALCISTA")
    
    result = analyze_symbol_smc(symbol, df_h1, df_m15)
    
    print(f"\n✓ Analysis completed for {symbol}")
    print(f"  - Tendencia H1: {result['tendencia_h1']}")
    print(f"  - Tendencia M15: {result['tendencia_m15']}")
    print(f"  - Último evento M15: {result['ultimo_evento_m15']}")
    print(f"  - Precio: {result['price']:.2f}")
    print(f"  - Score: {result['score']}")
    print(f"  - Estado: {result['estado']}")
    
    # Verify we're NOT getting "--" for trends
    if result['tendencia_h1'] != "--" and result['tendencia_m15'] != "--":
        print("\n✅ PASSED: Real trends calculated (not '--')")
    else:
        print("\n❌ FAILED: Got '--' for trends")
        return False
    
    # Test with Crash symbol
    print(f"\n{'='*60}")
    symbol = "Crash 1000 Index"
    df_h1 = create_sample_data(100, "BAJISTA")
    df_m15 = create_sample_data(100, "BAJISTA")
    
    result = analyze_symbol_smc(symbol, df_h1, df_m15)
    
    print(f"✓ Analysis completed for {symbol}")
    print(f"  - Tendencia H1: {result['tendencia_h1']}")
    print(f"  - Tendencia M15: {result['tendencia_m15']}")
    print(f"  - Último evento M15: {result['ultimo_evento_m15']}")
    print(f"  - Score: {result['score']}")
    print(f"  - Estado: {result['estado']}")
    
    if result['tendencia_h1'] != "--" and result['tendencia_m15'] != "--":
        print("\n✅ PASSED: Real trends calculated for CRASH")
    else:
        print("\n❌ FAILED: Got '--' for CRASH trends")
        return False
    
    return True

def test_direccion_operativa():
    """Test operational direction detection"""
    print("\n" + "="*60)
    print("TEST 5: Operational Direction")
    print("="*60)
    
    boom_dir = direccion_operativa_por_indice("Boom 1000 Index")
    crash_dir = direccion_operativa_por_indice("Crash 500 Index")
    other_dir = direccion_operativa_por_indice("EURUSD")
    
    print(f"✓ Boom 1000 Index: {boom_dir}")
    print(f"✓ Crash 500 Index: {crash_dir}")
    print(f"✓ EURUSD: {other_dir}")
    
    if boom_dir == "ALCISTA" and crash_dir == "BAJISTA" and other_dir is None:
        print("✅ PASSED")
        return True
    else:
        print("❌ FAILED")
        return False

if __name__ == "__main__":
    print("\n")
    print("="*60)
    print("SMC M15 SERVICE - UNIT TESTS")
    print("="*60)
    
    try:
        # Run tests
        swings = test_swings()
        eventos, tendencia = test_estructura(swings)
        fvgs = test_fvg()
        test_direccion_operativa()
        test_full_analysis()
        
        print("\n" + "="*60)
        print("ALL TESTS COMPLETED")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
