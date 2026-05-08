#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GreenTrading Desktop - Supabase Service
Servicio de comunicación con Supabase para persistencia de setups
"""

import os
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    from supabase import create_client, Client
except ImportError:
    print("ERROR: supabase-py not installed. Run: pip install supabase==2.3.0")
    raise

# Supabase configuration from environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

# Global Supabase client
_supabase_client: Optional[Client] = None


def init_supabase() -> Optional[Client]:
    """
    Initialize Supabase client with environment variables.
    
    Returns:
        Client instance or None if credentials missing
    """
    global _supabase_client
    
    if _supabase_client is not None:
        print("SUPABASE OK: Using existing client instance")
        return _supabase_client
    
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        print("SUPABASE ERROR: Credentials not configured")
        print("  Set SUPABASE_URL and SUPABASE_ANON_KEY in .env file")
        return None
    
    try:
        # Initialize Supabase client - compatible with version 2.3.0
        # Note: Do NOT pass proxy/proxies parameters as they're not supported
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        print(f"SUPABASE OK: Client initialized successfully")
        print(f"  URL: {SUPABASE_URL}")
        return _supabase_client
    except TypeError as e:
        if "proxy" in str(e) or "proxies" in str(e):
            print(f"SUPABASE ERROR: Proxy parameter not supported in this version: {e}")
            print("  Solution: Remove proxy/proxies parameters from create_client call")
        else:
            print(f"SUPABASE ERROR: TypeError initializing client: {e}")
        return None
    except Exception as e:
        print(f"SUPABASE ERROR: Error initializing Supabase client: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_client() -> Optional[Client]:
    """Get initialized Supabase client"""
    if _supabase_client is None:
        return init_supabase()
    return _supabase_client


# =========================
# CRUD OPERATIONS
# =========================

def create_setup(setup_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Create a new setup in green_trading_setups table.
    
    Args:
        setup_data: Setup data dictionary
    
    Returns:
        Created setup or None if error
    """
    client = get_client()
    if not client:
        return None
    
    try:
        # Add timestamps if not present
        if "created_at" not in setup_data:
            setup_data["created_at"] = datetime.now(timezone.utc).isoformat()
        if "updated_at" not in setup_data:
            setup_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        result = client.table("green_trading_setups").insert(setup_data).execute()
        
        if result.data:
            print(f"Setup created: {setup_data.get('symbol')} - {setup_data.get('strategy_id')}")
            return result.data[0]
        return None
    except Exception as e:
        print(f"ERROR: Error creating setup: {e}")
        return None


def update_setup(setup_id: int, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Update an existing setup by ID.
    
    Args:
        setup_id: Setup ID
        updates: Fields to update
    
    Returns:
        Updated setup or None if error
    """
    client = get_client()
    if not client:
        return None
    
    try:
        # Always update timestamp
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        result = client.table("green_trading_setups").update(updates).eq("id", setup_id).execute()
        
        if result.data:
            print(f"Setup updated: ID {setup_id}")
            return result.data[0]
        return None
    except Exception as e:
        print(f"ERROR: Error updating setup: {e}")
        return None


def get_active_setup(strategy_id: str, symbol: str, entrada: float, stoploss: float) -> Optional[Dict[str, Any]]:
    """
    Find an active setup by strategy, symbol, entrada and stoploss.
    
    Active setup = estado not in ('TP', 'SL', 'DESCARTADA')
    
    Args:
        strategy_id: Strategy ID (e.g., "SMC_M15_PRO")
        symbol: Symbol name
        entrada: Entry price
        stoploss: Stop loss price
    
    Returns:
        Setup dict or None if not found
    """
    client = get_client()
    if not client:
        print(f"SUPABASE ERROR: Cannot query active setup - client not initialized")
        return None
    
    try:
        print(f"SUPABASE: Querying active setup for {symbol}")
        print(f"  strategy_id: {strategy_id}")
        print(f"  entrada: {entrada}")
        print(f"  stoploss: {stoploss}")
        
        result = (
            client.table("green_trading_setups")
            .select("*")
            .eq("strategy_id", strategy_id)
            .eq("symbol", symbol)
            .eq("entrada", entrada)
            .eq("stoploss", stoploss)
            .not_.in_("estado", ["TP", "SL", "DESCARTADA"])
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        
        if result.data:
            setup = result.data[0]
            estado_previo = setup.get('estado')
            print(f"SUPABASE OK: estado_previo encontrado = {estado_previo}")
            print(f"  setup_id: {setup.get('id')}")
            print(f"  created_at: {setup.get('created_at')}")
            return setup
        else:
            print(f"SUPABASE: No estado_previo encontrado (nueva zona)")
            return None
    except Exception as e:
        print(f"SUPABASE ERROR: Error getting active setup for {symbol}: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_setup_history(
    symbol: Optional[str] = None,
    estado: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Get setup history with optional filters.
    
    Args:
        symbol: Filter by symbol (optional)
        estado: Filter by estado (optional)
        from_date: Filter from date (ISO format, optional)
        to_date: Filter to date (ISO format, optional)
        limit: Max results (default 100)
    
    Returns:
        List of setups
    """
    client = get_client()
    if not client:
        return []
    
    try:
        query = client.table("green_trading_setups").select("*")
        
        if symbol:
            query = query.eq("symbol", symbol)
        
        if estado:
            query = query.eq("estado", estado)
        
        if from_date:
            query = query.gte("created_at", from_date)
        
        if to_date:
            query = query.lte("created_at", to_date)
        
        result = query.order("created_at", desc=True).limit(limit).execute()
        
        return result.data if result.data else []
    except Exception as e:
        print(f"ERROR: Error getting setup history: {e}")
        return []


def get_tp_sl_summary() -> Dict[str, Dict[str, int]]:
    """
    Get TP/SL summary grouped by symbol.
    
    Returns:
        Dict with structure: {symbol: {tp: count, sl: count}}
    """
    client = get_client()
    if not client:
        return {}
    
    try:
        # Get all TP/SL setups
        result = (
            client.table("green_trading_setups")
            .select("symbol, estado")
            .in_("estado", ["TP", "SL"])
            .execute()
        )
        
        if not result.data:
            return {}
        
        # Group by symbol
        summary = {}
        for setup in result.data:
            symbol = setup["symbol"]
            estado = setup["estado"]
            
            if symbol not in summary:
                summary[symbol] = {"tp": 0, "sl": 0}
            
            if estado == "TP":
                summary[symbol]["tp"] += 1
            elif estado == "SL":
                summary[symbol]["sl"] += 1
        
        return summary
    except Exception as e:
        print(f"ERROR: Error getting TP/SL summary: {e}")
        return {}
