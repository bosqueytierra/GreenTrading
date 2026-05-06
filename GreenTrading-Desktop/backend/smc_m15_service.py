#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GreenTrading Desktop - SMC M15 Service
Phase 3: SMC analysis service for dashboard

Analyzes market data using SMC engines to provide:
- H1 trend
- M15 trend
- Last M15 event (BOS/CHOCH)
- Mother zone M15
- Score calculation
- OB/FVG/Barrida detection
- Setup state (ACTIVA/SIN_SETUP)
"""

import sys
import os
from datetime import datetime, timezone
import pandas as pd

# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, parent_dir)

try:
    from src.smc_engine import analyze_smc
except ImportError:
    print("Warning: SMC engine not available. Will return placeholder data.")
    analyze_smc = None


def analyze_symbol_smc(symbol: str, df_h1: pd.DataFrame, df_m15: pd.DataFrame) -> dict:
    """
    Analyze a symbol using SMC engine
    
    Args:
        symbol: Symbol name
        df_h1: H1 candles DataFrame
        df_m15: M15 candles DataFrame
    
    Returns:
        dict with SMC analysis results
    """
    # If engine not available or no data, return SIN SETUP
    if analyze_smc is None or df_h1 is None or df_m15 is None or len(df_h1) == 0 or len(df_m15) == 0:
        return create_sin_setup_response(symbol)
    
    try:
        # Run SMC analysis
        result = analyze_smc(df_h1, df_m15, df_m1=None)
        
        # Extract results
        tendencia_h1 = result.get('tendencia_h1', None)
        tendencia_m15 = result.get('tendencia_m15', None)
        eventos_m15 = result.get('eventos_m15', [])
        fvgs_m15 = result.get('fvgs_m15', [])
        zona = result.get('zona', None)
        precio_actual = result.get('precio_actual', None)
        
        # Determine if we have a valid setup
        if not zona or tendencia_h1 is None:
            return create_sin_setup_response(symbol, precio_actual)
        
        # Get last M15 event
        ultimo_evento_m15 = get_last_event(eventos_m15)
        
        # Check for OB in zone
        has_ob = check_order_block(zona)
        
        # Check for FVG in zone
        has_fvg = check_fvg_in_zone(zona, fvgs_m15)
        
        # Check for sweep (barrida)
        has_barrida = check_sweep(zona, df_m15)
        
        # Calculate score
        score = calculate_score(
            tendencia_h1=tendencia_h1,
            tendencia_m15=tendencia_m15,
            ultimo_evento_m15=ultimo_evento_m15,
            has_ob=has_ob,
            has_fvg=has_fvg,
            has_barrida=has_barrida
        )
        
        # Determine state
        estado = "ACTIVA" if score > 0 else "SIN SETUP"
        
        # Build response
        return {
            "symbol": symbol,
            "price": precio_actual,
            "tendencia_h1": format_trend(tendencia_h1),
            "tendencia_m15": format_trend(tendencia_m15),
            "ultimo_evento_m15": ultimo_evento_m15,
            "zona_madre_m15": {
                "desde": float(zona.get('desde', 0)),
                "hasta": float(zona.get('hasta', 0))
            } if zona else {"desde": 0, "hasta": 0},
            "score": score,
            "ob": "SÍ" if has_ob else "NO",
            "fvg": "SÍ" if has_fvg else "NO",
            "barrida": "SÍ" if has_barrida else "NO",
            "estado": estado,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        print(f"Error analyzing {symbol}: {e}")
        return create_sin_setup_response(symbol)


def create_sin_setup_response(symbol: str, price: float = None) -> dict:
    """
    Create a SIN SETUP response when no valid setup is found
    
    Args:
        symbol: Symbol name
        price: Current price (optional)
    
    Returns:
        dict with SIN SETUP structure
    """
    return {
        "symbol": symbol,
        "price": price,
        "tendencia_h1": "--",
        "tendencia_m15": "--",
        "ultimo_evento_m15": "SIN SETUP",
        "zona_madre_m15": {"desde": 0, "hasta": 0},
        "score": 0,
        "ob": "NO",
        "fvg": "NO",
        "barrida": "NO",
        "estado": "SIN SETUP",
        "updated_at": datetime.now(timezone.utc).isoformat()
    }


def format_trend(trend: str) -> str:
    """Format trend name"""
    if trend is None:
        return "--"
    return trend.upper()


def get_last_event(eventos: list) -> str:
    """
    Get last M15 event (BOS or CHOCH)
    
    Args:
        eventos: List of structure events
    
    Returns:
        Event string (BOS ALCISTA, CHOCH BAJISTA, etc.)
    """
    if not eventos or len(eventos) == 0:
        return "SIN EVENTO"
    
    # Get last event
    last = eventos[-1]
    tipo = last.get('tipo', '')
    sentido = last.get('sentido', '')
    
    if tipo and sentido:
        return f"{tipo} {sentido}".upper()
    
    return "SIN EVENTO"


def check_order_block(zona: dict) -> bool:
    """
    Check if zone has order block
    
    Args:
        zona: Zone dictionary
    
    Returns:
        True if zone has OB
    """
    if not zona:
        return False
    
    # Check if zone was created from an order block
    return zona.get('tipo', '') == 'OB' or zona.get('has_ob', False)


def check_fvg_in_zone(zona: dict, fvgs: list) -> bool:
    """
    Check if there's an FVG within the zone
    
    Args:
        zona: Zone dictionary
        fvgs: List of FVGs
    
    Returns:
        True if zone has FVG
    """
    if not zona or not fvgs:
        return False
    
    zona_desde = zona.get('desde', 0)
    zona_hasta = zona.get('hasta', 0)
    
    # Check if any FVG overlaps with zone
    for fvg in fvgs:
        fvg_desde = fvg.get('desde', 0)
        fvg_hasta = fvg.get('hasta', 0)
        
        # Check for overlap
        if not (fvg_hasta < zona_desde or fvg_desde > zona_hasta):
            return True
    
    return False


def check_sweep(zona: dict, df_m15: pd.DataFrame) -> bool:
    """
    Check for liquidity sweep (barrida)
    
    Args:
        zona: Zone dictionary
        df_m15: M15 DataFrame
    
    Returns:
        True if sweep detected
    """
    if not zona or df_m15 is None or len(df_m15) == 0:
        return False
    
    # Simple check: if zone has sweep flag
    return zona.get('has_sweep', False) or zona.get('barrida', False)


def calculate_score(tendencia_h1: str, tendencia_m15: str, ultimo_evento_m15: str,
                   has_ob: bool, has_fvg: bool, has_barrida: bool) -> int:
    """
    Calculate setup score
    
    Scoring:
    - H1 and M15 trends aligned: +3
    - H1 trend exists: +2
    - Valid M15 event (BOS/CHOCH): +2
    - Order Block: +1
    - FVG: +1
    - Sweep: +1
    
    Args:
        tendencia_h1: H1 trend
        tendencia_m15: M15 trend
        ultimo_evento_m15: Last M15 event
        has_ob: Has order block
        has_fvg: Has FVG
        has_barrida: Has sweep
    
    Returns:
        Score (0-10)
    """
    score = 0
    
    # Check trends
    if tendencia_h1 and tendencia_h1 != "--":
        score += 2
        
        # Bonus if aligned with M15
        if tendencia_m15 and tendencia_m15 != "--":
            if tendencia_h1 == tendencia_m15:
                score += 3
    
    # Check M15 event
    if ultimo_evento_m15 and ultimo_evento_m15 not in ["SIN EVENTO", "SIN SETUP", "--"]:
        score += 2
    
    # Add confluence indicators
    if has_ob:
        score += 1
    if has_fvg:
        score += 1
    if has_barrida:
        score += 1
    
    return score
