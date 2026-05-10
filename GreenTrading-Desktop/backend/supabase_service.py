#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GreenTrading Desktop - Supabase Service
Servicio de comunicación con Supabase para persistencia de setups
"""

import os
import inspect
import traceback
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env relative to this file, not CWD
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if os.path.exists(_env_path):
    load_dotenv(dotenv_path=_env_path)
    print(f"ENV LOAD: .env encontrado en {_env_path}")
else:
    # Fallback: search upward from this file
    load_dotenv()
    print(f"ENV LOAD: .env no encontrado en {_env_path}, usando busqueda automatica")

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
_supabase_proxy_patch_applied = False


def _mask_supabase_key(key: Optional[str]) -> str:
    """Mask Supabase key for logs without exposing the full value."""
    if not key:
        return "(NO CONFIGURADA)"
    if len(key) <= 12:
        return "(CONFIGURADA)"
    return f"{key[:8]}...{key[-4:]}"


def _apply_supabase_proxy_compatibility_patch() -> None:
    """Patch gotrue/httpx proxy arg mismatch for older httpx versions."""
    global _supabase_proxy_patch_applied

    if _supabase_proxy_patch_applied:
        return

    try:
        import httpx
        from gotrue._sync import gotrue_base_api
    except ImportError:
        return

    httpx_client_params = inspect.signature(httpx.Client.__init__).parameters

    if "proxy" in httpx_client_params or "proxies" not in httpx_client_params:
        _supabase_proxy_patch_applied = True
        return

    if getattr(gotrue_base_api.SyncGoTrueBaseAPI, "_greentrading_proxy_compat", False):
        _supabase_proxy_patch_applied = True
        return

    def _compat_init(
        self,
        *,
        url: str,
        headers: Dict[str, str],
        http_client: Optional["httpx.Client"],
        verify: bool = True,
        proxy: Optional[str] = None,
    ):
        self._url = url
        self._headers = headers

        if http_client is not None:
            self._http_client = http_client
            return

        client_kwargs = {
            "verify": bool(verify),
            "follow_redirects": True,
            "http2": True,
        }

        if proxy is not None:
            client_kwargs["proxies"] = proxy

        self._http_client = httpx.Client(**client_kwargs)

    gotrue_base_api.SyncGoTrueBaseAPI.__init__ = _compat_init
    gotrue_base_api.SyncGoTrueBaseAPI._greentrading_proxy_compat = True
    _supabase_proxy_patch_applied = True
    print("SUPABASE OK: Applied httpx proxy compatibility patch")


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
    
    # Log env values for diagnostics (mask key)
    url_diag = SUPABASE_URL if SUPABASE_URL else "(NO CONFIGURADA)"
    key_diag = _mask_supabase_key(SUPABASE_ANON_KEY)
    print(f"ENV CHECK: SUPABASE_URL = {url_diag}")
    print(f"ENV CHECK: SUPABASE_ANON_KEY = {key_diag}")

    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        print("SUPABASE ERROR: Credentials not configured")
        print("  Set SUPABASE_URL and SUPABASE_ANON_KEY in .env file")
        return None
    
    try:
        _apply_supabase_proxy_compatibility_patch()
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
        
        print(f"SUPABASE INSERT INTENT: tabla=green_trading_setups")
        print(f"  symbol: {setup_data.get('symbol')}")
        print(f"  strategy_id: {setup_data.get('strategy_id')}")
        print(f"  estado: {setup_data.get('estado')}")
        print(f"  entrada: {setup_data.get('entrada')}")
        print(f"  stoploss: {setup_data.get('stoploss')}")
        print(f"  payload completo: {setup_data}")
        
        result = client.table("green_trading_setups").insert(setup_data).execute()
        
        if result.data:
            print(f"SUPABASE OK: Setup creado - {setup_data.get('symbol')} / {setup_data.get('strategy_id')} / id={result.data[0].get('id')}")
            return result.data[0]
        else:
            print(f"SUPABASE WARNING: insert ejecutado pero sin data retornada. result={result}")
            return None
    except Exception as e:
        print(f"SUPABASE ERROR: Error creando setup: {e}")
        traceback.print_exc()
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
        
        print(f"SUPABASE UPDATE INTENT: tabla=green_trading_setups, id={setup_id}")
        print(f"  updates: {updates}")
        
        result = client.table("green_trading_setups").update(updates).eq("id", setup_id).execute()
        
        if result.data:
            print(f"SUPABASE OK: Setup actualizado - ID {setup_id}")
            return result.data[0]
        else:
            print(f"SUPABASE WARNING: update ejecutado pero sin data retornada. result={result}")
            return None
    except Exception as e:
        print(f"SUPABASE ERROR: Error actualizando setup ID {setup_id}: {e}")
        traceback.print_exc()
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
        traceback.print_exc()
        return None


def get_active_setup_by_symbol(strategy_id: str, symbol: str) -> Optional[Dict[str, Any]]:
    """
    Find any active (non-terminal) setup for a symbol, regardless of entrada/stoploss.

    Used for MODO SEGUIMIENTO: once a zone is active, track it until TP or SL
    without requiring the caller to know the exact entrada/stoploss values.

    Active setup = estado not in ('TP', 'SL', 'DESCARTADA')

    Args:
        strategy_id: Strategy ID (e.g., "SMC_M15_PRO")
        symbol: Symbol name

    Returns:
        Most recent non-terminal setup dict, or None if not found
    """
    client = get_client()
    if not client:
        print(f"SUPABASE ERROR: Cannot query active setup by symbol - client not initialized")
        return None

    try:
        print(f"SUPABASE: Querying active setup by symbol for {symbol}")
        print(f"  strategy_id: {strategy_id}")

        result = (
            client.table("green_trading_setups")
            .select("*")
            .eq("strategy_id", strategy_id)
            .eq("symbol", symbol)
            .not_.in_("estado", ["TP", "SL", "DESCARTADA"])
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        if result.data:
            setup = result.data[0]
            estado_previo = setup.get('estado')
            print(f"SUPABASE OK: setup activo encontrado para {symbol}")
            print(f"  estado: {estado_previo}")
            print(f"  setup_id: {setup.get('id')}")
            print(f"  entrada: {setup.get('entrada')}")
            print(f"  stoploss: {setup.get('stoploss')}")
            print(f"  tp_1_1: {setup.get('tp_1_1')}")
            return setup
        else:
            print(f"SUPABASE: No hay setup activo para {symbol} (MODO BUSQUEDA)")
            return None
    except Exception as e:
        print(f"SUPABASE ERROR: Error getting active setup by symbol for {symbol}: {e}")
        traceback.print_exc()
        return None


def get_setup_history(
    symbol: Optional[str] = None,
    estado: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: int = 100,
    terminal_only: bool = True
) -> List[Dict[str, Any]]:
    """
    Get setup history with optional filters.
    
    Args:
        symbol: Filter by symbol (optional)
        estado: Filter by estado (optional)
        from_date: Filter from date (ISO format, optional)
        to_date: Filter to date (ISO format, optional)
        limit: Max results (default 100)
        terminal_only: If True, only return closed setups (TP/SL)
    
    Returns:
        List of setups
    """
    client = get_client()
    if not client:
        return []
    
    try:
        query = client.table("green_trading_setups").select("*")

        # Historial cerrado por defecto: solo operaciones finalizadas
        if terminal_only:
            query = query.in_("estado", ["TP", "SL"])
        
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
