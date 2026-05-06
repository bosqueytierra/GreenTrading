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
from datetime import datetime, timezone
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import MetaTrader5 as mt5
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn
except ImportError as e:
    print(f"❌ ERROR: Missing dependency: {e}")
    print("Please install: pip install fastapi uvicorn MetaTrader5")
    sys.exit(1)

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


def init_mt5():
    """Initialize MT5 connection"""
    global mt5_initialized, mt5_terminal_info
    
    if mt5_initialized:
        return True
    
    print("🔌 Initializing MT5 connection...")
    
    if not mt5.initialize():
        error = mt5.last_error()
        print(f"❌ MT5 initialization failed: {error}")
        return False
    
    mt5_initialized = True
    terminal_info = mt5.terminal_info()
    if terminal_info:
        mt5_terminal_info = terminal_info.name
        print(f"✅ MT5 connected: {mt5_terminal_info}")
    else:
        print("✅ MT5 connected")
    
    return True


def shutdown_mt5():
    """Shutdown MT5 connection"""
    global mt5_initialized
    if mt5_initialized:
        mt5.shutdown()
        mt5_initialized = False
        print("🛑 MT5 disconnected")


@app.on_event("startup")
async def startup_event():
    """Initialize MT5 on startup"""
    print("🚀 Starting GreenTrading Desktop API...")
    init_mt5()


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    print("🛑 Shutting down GreenTrading Desktop API...")
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
    print(f"📊 Reading candle: {symbol} @ {timeframe}")
    
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
        rates = mt5.copy_rates_from_pos(symbol, mt5_timeframe, 1, 1)
        
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
        
        print(f"✅ Candle read successfully: {symbol} @ {timeframe}")
        return result
        
    except Exception as e:
        print(f"❌ Error reading candle: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {str(e)}"
        )


if __name__ == "__main__":
    print("=" * 60)
    print("🚀 GreenTrading Desktop - Python Backend")
    print("=" * 60)
    print("Phase 1: Minimal API Server")
    print("Architecture: Event-driven, in-memory processing")
    print("=" * 60)
    
    # Run FastAPI server
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8765,
        log_level="info"
    )
