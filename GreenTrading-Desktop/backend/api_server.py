#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GreenTrading Desktop - Python Backend API Server
Phase 1: Minimal FastAPI server with MT5 connection

Architecture:
- FastAPI REST API on localhost:8765
- MT5 connection for reading candles
- Event-driven architecture (future: WebSockets)
- NO SQLite dependency (pure in-memory processing)
"""

import sys
import os
import time
import traceback
from datetime import datetime, timezone
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import MetaTrader5 as mt5
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn
    import pandas as pd
except ImportError as e:
    print(f"ERROR: Missing dependency: {e}")
    print("Please install: pip install fastapi uvicorn MetaTrader5 pandas")
    sys.exit(1)

# Import SMC service
try:
    from smc_m15_service import analyze_symbol_smc, create_sin_setup_response
except ImportError:
    print("WARNING: SMC service not available")
    analyze_symbol_smc = None
    create_sin_setup_response = None

# Import Supabase service
try:
    import supabase_service
except ImportError:
    print("WARNING: Supabase service not available")
    supabase_service = None

# FastAPI app
app = FastAPI(
    title="GreenTrading Desktop API",
    description="Local API for MT5 integration",
    version="0.1.0"
)

# CORS (allow Electron frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
mt5_initialized = False
mt5_terminal_info = None

# Timeframe mapping
TIMEFRAME_MAP = {
    'M1': mt5.TIMEFRAME_M1,
    'M15': mt5.TIMEFRAME_M15,
    'H1': mt5.TIMEFRAME_H1,
}

# Phase 2: 10 symbols for dashboard
DASHBOARD_SYMBOLS = [
    "Boom 1000 Index",
    "Boom 900 Index",
    "Boom 600 Index",
    "Boom 500 Index",
    "Boom 300 Index",
    "Crash 1000 Index",
    "Crash 900 Index",
    "Crash 600 Index",
    "Crash 500 Index",
    "Crash 300 Index",
]


def init_mt5():
    """Initialize MT5 connection"""
    global mt5_initialized, mt5_terminal_info
    
    if mt5_initialized:
        return True
    
    print("Initializing MT5 connection...")
    
    if not mt5.initialize():
        error = mt5.last_error()
        print(f"MT5 initialization failed: {error}")
        return False
    
    mt5_initialized = True
    terminal_info = mt5.terminal_info()
    if terminal_info:
        mt5_terminal_info = terminal_info.name
        print(f"MT5 connected: {mt5_terminal_info}")
    else:
        print("MT5 connected")
    
    return True


def shutdown_mt5():
    """Shutdown MT5 connection"""
    global mt5_initialized
    if mt5_initialized:
        mt5.shutdown()
        mt5_initialized = False
        print("MT5 disconnected")


@app.on_event("startup")
async def startup_event():
    """Initialize MT5 and Supabase on startup"""
    print("Starting GreenTrading Desktop API...")
    init_mt5()
    
    # Initialize Supabase
    if supabase_service:
        supabase_service.init_supabase()
        print("Supabase initialized")
    else:
        print("WARNING: Supabase service not available")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    print("Shutting down GreenTrading Desktop API...")
    shutdown_mt5()


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "GreenTrading Desktop API",
        "version": "0.1.0",
        "phase": "1 - Proof of Concept",
        "status": "running"
    }


@app.get("/api/status")
async def get_status():
    """
    Get backend and MT5 status
    
    Returns:
        dict: Status information
    """
    return {
        "backend_running": True,
        "mt5_connected": mt5_initialized,
        "mt5_terminal_info": mt5_terminal_info,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


def read_candle_data(symbol: str, timeframe: str) -> Optional[dict]:
    """
    Helper function to read one candle from MT5
    
    Args:
        symbol: Symbol name
        timeframe: Timeframe code (M1, M15, H1)
    
    Returns:
        dict with candle data or None if error
    """
    if not mt5_initialized:
        return None
    
    if timeframe not in TIMEFRAME_MAP:
        return None
    
    mt5_timeframe = TIMEFRAME_MAP[timeframe]
    
    try:
        rates = mt5.copy_rates_from_pos(symbol, mt5_timeframe, 0, 1)
        
        if rates is None or len(rates) == 0:
            return None
        
        candle = rates[0]
        
        return {
            "time": datetime.fromtimestamp(candle['time'], tz=timezone.utc).isoformat(),
            "open": float(candle['open']),
            "high": float(candle['high']),
            "low": float(candle['low']),
            "close": float(candle['close']),
            "tick_volume": int(candle['tick_volume']),
            "spread": int(candle['spread']),
            "real_volume": int(candle['real_volume'])
        }
    except Exception as e:
        print(f"Error reading candle {symbol} @ {timeframe}: {e}")
        return None


def read_candles_dataframe(symbol: str, timeframe: str, count: int = 100) -> Optional[pd.DataFrame]:
    """
    Helper function to read multiple candles from MT5 as DataFrame
    
    Args:
        symbol: Symbol name
        timeframe: Timeframe code (M1, M15, H1)
        count: Number of candles to read (default: 100)
    
    Returns:
        DataFrame with candle data or None if error
    """
    if not mt5_initialized:
        return None
    
    if timeframe not in TIMEFRAME_MAP:
        return None
    
    mt5_timeframe = TIMEFRAME_MAP[timeframe]
    
    try:
        rates = mt5.copy_rates_from_pos(symbol, mt5_timeframe, 0, count)
        
        if rates is None or len(rates) == 0:
            return None
        
        # Convert to DataFrame
        df = pd.DataFrame(rates)
        
        # Convert time to datetime
        df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
        
        # Ensure proper column types
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        
        return df
        
    except Exception as e:
        print(f"Error reading candles {symbol} @ {timeframe}: {e}")
        return None


@app.get("/api/symbols/snapshot")
async def get_symbols_snapshot():
    """
    Phase 2: Get snapshot of all dashboard symbols
    
    Returns array with 10 symbols and their latest data:
    - symbol
    - price (current price from last M1 candle close)
    - m1_last_candle
    - m15_last_candle
    - h1_last_candle
    - updated_at
    - mt5_connected
    
    Returns:
        list: Array of symbol snapshots
    """
    print("Reading snapshot for all dashboard symbols...")
    
    # Validate MT5 connection
    if not mt5_initialized:
        if not init_mt5():
            raise HTTPException(
                status_code=503,
                detail="MT5 not connected. Please ensure MT5 is running."
            )
    
    snapshots = []
    timestamp = datetime.now(timezone.utc).isoformat()
    
    for symbol in DASHBOARD_SYMBOLS:
        # Read candles for all timeframes
        m1_candle = read_candle_data(symbol, 'M1')
        m15_candle = read_candle_data(symbol, 'M15')
        h1_candle = read_candle_data(symbol, 'H1')
        
        # Get current price from M1 close (defensive coding)
        price = m1_candle.get('close') if m1_candle else None
        
        snapshot = {
            "symbol": symbol,
            "price": price,
            "m1_last_candle": m1_candle,
            "m15_last_candle": m15_candle,
            "h1_last_candle": h1_candle,
            "updated_at": timestamp,
            "mt5_connected": mt5_initialized
        }
        
        snapshots.append(snapshot)
    
    print(f"Snapshot complete: {len(snapshots)} symbols read")
    return snapshots


@app.get("/api/candle/{symbol}/{timeframe}")
async def get_candle(symbol: str, timeframe: str):
    """
    Get the latest candle from MT5
    
    Phase 1: Read ONE candle in real-time from MT5
    NO database, NO storage, pure in-memory processing
    
    Args:
        symbol: Symbol name (e.g., "Boom 1000 Index")
        timeframe: Timeframe code (M1, M15, H1)
    
    Returns:
        dict: Candle data
    """
    print(f"Reading candle: {symbol} @ {timeframe}")
    
    # Validate MT5 connection
    if not mt5_initialized:
        if not init_mt5():
            raise HTTPException(
                status_code=503,
                detail="MT5 not connected. Please ensure MT5 is running."
            )
    
    # Validate timeframe
    if timeframe not in TIMEFRAME_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timeframe. Use: {', '.join(TIMEFRAME_MAP.keys())}"
        )
    
    mt5_timeframe = TIMEFRAME_MAP[timeframe]
    
    # Read ONE candle from MT5 (most recent completed candle)
    try:
        rates = mt5.copy_rates_from_pos(symbol, mt5_timeframe, 0, 1)
        
        if rates is None or len(rates) == 0:
            error = mt5.last_error()
            raise HTTPException(
                status_code=404,
                detail=f"Failed to read candle from MT5: {error}"
            )
        
        # Extract candle data
        candle = rates[0]
        
        # Format response
        result = {
            "symbol": symbol,
            "timeframe": timeframe,
            "candle": {
                "time": datetime.fromtimestamp(candle['time'], tz=timezone.utc).isoformat(),
                "open": float(candle['open']),
                "high": float(candle['high']),
                "low": float(candle['low']),
                "close": float(candle['close']),
                "tick_volume": int(candle['tick_volume']),
                "spread": int(candle['spread']),
                "real_volume": int(candle['real_volume'])
            },
            "read_at": datetime.now(timezone.utc).isoformat()
        }
        
        print(f"Candle read successfully: {symbol} @ {timeframe}")
        return result
        
    except Exception as e:
        print(f"Error reading candle: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {str(e)}"
        )


@app.get("/api/smc/m15-pro/snapshot")
async def get_smc_m15_pro_snapshot():
    """
    Phase 3: Get SMC M15 PRO snapshot for all dashboard symbols
    
    Returns array with SMC analysis for each symbol:
    - symbol
    - price
    - tendencia_h1
    - tendencia_m15
    - ultimo_evento_m15
    - zona_madre_m15 (desde, hasta)
    - score
    - ob (SÍ/NO)
    - fvg (SÍ/NO)
    - barrida (SÍ/NO)
    - estado (ACTIVA/SIN SETUP)
    - updated_at
    
    Returns:
        list: Array of SMC snapshots
    """
    print("SNAPSHOT ENDPOINT HIT")
    print("Reading SMC M15 PRO snapshot for all dashboard symbols...")
    print("Candle configuration (matching master_bot.py):")
    print("  - H1 candles requested: 500")
    print("  - M15 candles requested: 800")
    print("  - M1 candles: 600 (configured for future use, not actively fetched yet)")
    
    # Validate MT5 connection
    if not mt5_initialized:
        if not init_mt5():
            raise HTTPException(
                status_code=503,
                detail="MT5 not connected. Please ensure MT5 is running."
            )
    
    # Check if SMC service is available
    if analyze_symbol_smc is None or create_sin_setup_response is None:
        print("WARNING: SMC service not available, returning placeholder data")
        # Return placeholder data for all symbols
        snapshots = []
        for symbol in DASHBOARD_SYMBOLS:
            m1_candle = read_candle_data(symbol, 'M1')
            price = m1_candle.get('close') if m1_candle else None
            
            snapshots.append({
                "symbol": symbol,
                "price": price,
                "tendencia_h1": "--",
                "tendencia_m15": "--",
                "ultimo_evento_m15": "SIN SETUP",
                "zona_madre_m15": {"desde": 0, "hasta": 0},
                "entrada": None,
                "stoploss": None,
                "tp_1_1": None,
                "score": 0,
                "ob": "NO",
                "fvg": "NO",
                "barrida": "NO",
                "estado": "SIN SETUP",
                "updated_at": datetime.now(timezone.utc).isoformat()
            })
        
        return snapshots
    
    snapshots = []
    snapshot_start = time.time()
    
    try:
        for symbol in DASHBOARD_SYMBOLS:
            symbol_start = time.time()
            print(f"SYMBOL START: {symbol}")
            try:
                # Read candles for H1 and M15 (matching master_bot.py)
                # master_bot.py uses: H1=500, M15=800, M1=600
                df_h1 = read_candles_dataframe(symbol, 'H1', count=500)
                df_m15 = read_candles_dataframe(symbol, 'M15', count=800)
                df_m1 = read_candles_dataframe(symbol, 'M1', count=30)
                
                # Analyze symbol with SMC engine
                smc_result = analyze_symbol_smc(symbol, df_h1, df_m15, df_m1)
                
                # If no price yet, get it from M1
                if smc_result['price'] is None:
                    m1_candle = read_candle_data(symbol, 'M1')
                    smc_result['price'] = m1_candle.get('close') if m1_candle else None
                
                snapshots.append(smc_result)
                symbol_ms = int((time.time() - symbol_start) * 1000)
                print(f"SYMBOL DONE: {symbol} {symbol_ms}ms")
                
            except Exception as e:
                symbol_ms = int((time.time() - symbol_start) * 1000)
                print(f"SYMBOL ERROR: {symbol} {symbol_ms}ms - {e}")
                traceback.print_exc()
                # Add SIN SETUP response for failed symbol - try service first, then minimal safe fallback
                try:
                    m1_candle = read_candle_data(symbol, 'M1')
                    price = m1_candle.get('close') if m1_candle else None
                    snapshots.append(create_sin_setup_response(symbol, price))
                except Exception as fallback_e:
                    print(f"Error creating fallback for {symbol}: {fallback_e}")
                    # Emergency minimal response - keeps socket alive, frontend handles missing fields
                    snapshots.append({
                        "symbol": symbol,
                        "price": None,
                        "estado": "SIN SETUP",
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    })
    except Exception as outer_e:
        print(f"CRITICAL ERROR in snapshot loop: {outer_e}")
        traceback.print_exc()
        # Return whatever snapshots we collected so far rather than closing socket
        if not snapshots:
            return []
    
    total_ms = int((time.time() - snapshot_start) * 1000)
    print(f"SNAPSHOT TOTAL: {total_ms}ms")
    print(f"SNAPSHOT RETURNING {len(snapshots)} rows")
    return snapshots


# =========================
# SUPABASE ENDPOINTS
# =========================

@app.post("/api/setups")
async def create_or_update_setup(setup_data: dict):
    """
    Create or update a setup in Supabase.
    
    If an active setup exists with same strategy_id + symbol + entrada + stoploss,
    it will be updated. Otherwise, a new setup will be created.
    
    Request body:
        {
            "strategy_id": "SMC_M15_PRO",
            "strategy_name": "SMC M15 PRO",
            "symbol": "Boom 1000 Index",
            "tendencia_h1": "ALCISTA",
            "tendencia_m15": "ALCISTA",
            "ultimo_evento_m15": "CHOCH ALCISTA",
            "entrada": 1234.56,
            "stoploss": 1230.00,
            "tp_1_1": 1239.12,
            "score": 3,
            "ob": true,
            "fvg": true,
            "barrida": true,
            "estado": "ESPERANDO_ENTRADA",
            "estado_dashboard": "ESPERANDO_ENTRADA",
            "precio_detectado": 1250.00,
            "precio_actual": 1250.00
        }
    
    Returns:
        Created or updated setup
    """
    if not supabase_service:
        raise HTTPException(status_code=503, detail="Supabase service not available")
    
    try:
        # Extract key fields
        strategy_id = setup_data.get("strategy_id")
        symbol = setup_data.get("symbol")
        entrada = setup_data.get("entrada")
        stoploss = setup_data.get("stoploss")
        
        if not all([strategy_id, symbol, entrada is not None, stoploss is not None]):
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        # Check if active setup exists
        existing = supabase_service.get_active_setup(strategy_id, symbol, entrada, stoploss)
        
        if existing:
            # Update existing setup
            setup_id = existing["id"]
            updates = {
                "estado": setup_data.get("estado"),
                "estado_dashboard": setup_data.get("estado_dashboard"),
                "precio_actual": setup_data.get("precio_actual")
            }
            result = supabase_service.update_setup(setup_id, updates)
            return {"success": True, "action": "updated", "data": result}
        else:
            # Create new setup
            result = supabase_service.create_setup(setup_data)
            return {"success": True, "action": "created", "data": result}
            
    except Exception as e:
        print(f"Error in create_or_update_setup: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/setups/active")
async def get_active_setup_endpoint(
    strategy_id: str,
    symbol: str,
    entrada: float,
    stoploss: float
):
    """
    Get an active setup by strategy, symbol, entrada and stoploss.
    
    Query parameters:
        - strategy_id: Strategy ID (e.g., "SMC_M15_PRO")
        - symbol: Symbol name
        - entrada: Entry price
        - stoploss: Stop loss price
    
    Returns:
        Setup dict or null if not found
    """
    if not supabase_service:
        raise HTTPException(status_code=503, detail="Supabase service not available")
    
    try:
        result = supabase_service.get_active_setup(strategy_id, symbol, entrada, stoploss)
        return {"success": True, "data": result}
    except Exception as e:
        print(f"Error in get_active_setup: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/setups/history")
async def get_setup_history_endpoint(
    symbol: Optional[str] = None,
    estado: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: int = 100
):
    """
    Get setup history with optional filters.
    
    Query parameters:
        - symbol: Filter by symbol (optional)
        - estado: Filter by estado (optional)
        - from_date: Filter from date ISO format (optional)
        - to_date: Filter to date ISO format (optional)
        - limit: Max results (default 100)
    
    Returns:
        List of setups
    """
    if not supabase_service:
        raise HTTPException(status_code=503, detail="Supabase service not available")
    
    try:
        result = supabase_service.get_setup_history(
            symbol=symbol,
            estado=estado,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            terminal_only=True
        )
        print(f"HISTORIAL OK: returned {len(result)} setups from Supabase")
        return {"success": True, "setups": result, "count": len(result), "data": result}
    except Exception as e:
        print(f"HISTORIAL ERROR: Error in get_setup_history: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/setups/summary")
async def get_tp_sl_summary_endpoint():
    """
    Get TP/SL summary grouped by symbol.
    
    Returns:
        Dict with structure: {symbol: {tp: count, sl: count}}
    """
    if not supabase_service:
        raise HTTPException(status_code=503, detail="Supabase service not available")
    
    try:
        result = supabase_service.get_tp_sl_summary()
        return {"success": True, "data": result}
    except Exception as e:
        print(f"Error in get_tp_sl_summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    print("=" * 60)
    print("GreenTrading Desktop - Python Backend")
    print("=" * 60)
    print("Phase 1: Minimal API Server")
    print("Architecture: Event-driven, in-memory processing")
    print("=" * 60)
    print("API_SERVER_PATH:", __file__)
    
    # Run FastAPI server
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8765,
        log_level="info"
    )
