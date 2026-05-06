# Architecture Clarification - Candle Processing & Storage

**Date**: 2026-05-06  
**Status**: Important architectural clarification

---

## 🎯 Key Clarification

### What We DON'T Want
❌ Store ALL candles in SQLite (like Supabase model)

### What We DO Want

#### 1. Engine Reads Directly from MT5
✅ **The engine CAN and SHOULD read from MT5 whatever number of candles it needs**

- Engine requests candles directly from MT5 via MetaTrader5 API
- Engine reads the quantity needed for correct calculation (e.g., 500-1000+ candles for SMC analysis)
- No intermediate storage required for engine processing
- Fresh data directly from source

**Example:**
```python
# Engine reads what it needs from MT5
candles_m15 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 1000)
candles_h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 500)

# Process in memory
results = smc_engine.analyze(candles_m15, candles_h1)

# Save ONLY results to SQLite
save_setups_to_sqlite(results)
```

#### 2. Candles: Read → Process → Discard
✅ **Candles are ephemeral during processing**

```
MT5 → Read candles → Process in memory → Discard candles
                           ↓
                    Save RESULTS to SQLite
```

- Candles are read from MT5
- Processed in memory (DataFrames, calculations)
- Discarded after processing
- Only RESULTS are persisted

#### 3. SQLite Stores LIMITED Buffer (Optional)
✅ **OPTIONAL: Small buffer of recent candles for quick access**

- **Purpose**: Avoid re-reading from MT5 for recent data
- **Size**: Maximum 300-500 candles per symbol/timeframe
- **Management**: FIFO queue (oldest removed as new arrive)
- **Usage**: Quick access to recent context without MT5 query

**Important**: This is OPTIONAL optimization, not required for Phase 1

```python
class CandleBuffer:
    """Optional: Limited in-memory or SQLite buffer"""
    def __init__(self, max_size=500):
        self.buffer = deque(maxlen=max_size)
    
    def add(self, candle):
        self.buffer.append(candle)  # Auto-removes oldest
    
    def get_recent(self, count=100):
        return list(self.buffer)[-count:]
```

#### 4. History Storage: Pre-Calculated Results
✅ **History is COMPLETE but as PROCESSED RESULTS**

**What SQLite stores:**
- ✅ Setups (zones detected)
- ✅ Zone boundaries (high, low)
- ✅ States (ACTIVA, EN_ZONA, PROFIT, PAUSADA, TP, SL)
- ✅ Timestamps (setup_time, entry_time, exit_time)
- ✅ Results (TP/SL hit, profit/loss in points)
- ✅ Metadata (strategy, symbol, timeframe)
- ✅ Indicators at setup creation (H1 trend, M15 event, etc.)

**What SQLite does NOT store:**
- ❌ All historical candles
- ❌ Raw OHLC data for every timeframe
- ❌ Intermediate calculations

**Critical Point:**
> **History does NOT depend on recalculating old candles**

When displaying history, we show:
- Pre-calculated setups with their results
- Timestamps of when events occurred
- Final outcomes (TP/SL)
- NO recalculation needed

**Example History Record:**
```python
{
    'id': 123,
    'symbol': 'Boom 1000 Index',
    'strategy': 'SMC_M15_PRO',
    'setup_time': '2026-05-06T10:00:00Z',
    'zona_high': 12345.67,
    'zona_low': 12340.50,
    'entry_price': 12342.00,
    'tp_price': 12350.00,
    'sl_price': 12338.00,
    'estado': 'TP',
    'resultado_puntos': 8.0,
    'h1_trend': 'ALCISTA',
    'm15_event': 'BOS',
    'created_at': '2026-05-06T10:00:00Z',
    'closed_at': '2026-05-06T12:30:00Z'
}
```

This record is complete - no need to recalculate anything.

---

## 🏗️ Complete Data Flow

### Real-Time Processing (Phase 2+)

```
┌─────────────────────────────────────────────────────────┐
│  1. Monitor MT5 for new candles                         │
│     - Check every second for new completed candles      │
└────────────────────┬────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────┐
│  2. Read candles from MT5 (engine needs)                │
│     - M15: Read last 1000 candles                       │
│     - H1:  Read last 500 candles                        │
│     - Direct from MT5 API                               │
└────────────────────┬────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────┐
│  3. Process in memory (SMC Engine)                      │
│     - Detect swings                                     │
│     - Find BOS/CHOCH                                    │
│     - Identify FVG                                      │
│     - Create zones                                      │
│     - Calculate TP/SL                                   │
│     (All in RAM - DataFrames, NumPy arrays)            │
└────────────────────┬────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────┐
│  4. Save RESULTS to SQLite                              │
│     - New setups detected → INSERT                      │
│     - Setup state changes → UPDATE                      │
│     - Zone triggered → UPDATE estado                    │
│     - TP/SL hit → UPDATE estado, resultado              │
└────────────────────┬────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────┐
│  5. Emit event to Electron                              │
│     - WebSocket: "setup_created"                        │
│     - WebSocket: "setup_updated"                        │
└────────────────────┬────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────┐
│  6. UI updates                                           │
│     - Dashboard refreshes                               │
│     - History updates                                   │
│     (No polling, event-driven)                         │
└─────────────────────────────────────────────────────────┘
```

### History Viewing (Phase 2+)

```
User opens History tab
         ↓
Query SQLite: SELECT * FROM smc_m15_setups 
              WHERE estado IN ('TP', 'SL', 'PROFIT')
              ORDER BY closed_at DESC
         ↓
Display pre-calculated results
         ↓
NO need to read/recalculate candles ✅
```

---

## 💾 SQLite Schema (Future Phases)

### Main Tables

#### 1. Setup Tables (One per strategy)

```sql
-- SMC M15 PRO setups
CREATE TABLE smc_m15_setups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    strategy TEXT DEFAULT 'SMC_M15_PRO',
    
    -- Timestamps
    setup_time TIMESTAMP NOT NULL,
    entry_time TIMESTAMP,
    closed_at TIMESTAMP,
    
    -- Zone definition
    zona_high REAL NOT NULL,
    zona_low REAL NOT NULL,
    zona_size_puntos REAL,
    
    -- Trade parameters
    entry_price REAL,
    tp_price REAL,
    sl_price REAL,
    
    -- State
    estado TEXT NOT NULL,  -- ACTIVA, EN_ZONA, PROFIT, PAUSADA, TP, SL
    motivo_cierre TEXT,
    resultado_puntos REAL,
    
    -- Context at creation (pre-calculated)
    h1_trend TEXT,
    m15_event TEXT,
    m15_trend TEXT,
    fvg_present BOOLEAN,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes
    INDEX idx_symbol_estado (symbol, estado),
    INDEX idx_setup_time (setup_time),
    INDEX idx_estado (estado)
);
```

#### 2. Optional: Limited Candle Buffer

```sql
-- OPTIONAL: Recent candles buffer (300-500 per symbol/timeframe)
CREATE TABLE candle_buffer (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    tick_volume INTEGER,
    
    -- Auto-cleanup old records
    UNIQUE(symbol, timeframe, timestamp)
);

-- Cleanup policy: Keep only last 500 per symbol/timeframe
-- Implemented in code, not database trigger
```

#### 3. Metrics Table

```sql
CREATE TABLE metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    
    -- Counters
    tp_count INTEGER DEFAULT 0,
    sl_count INTEGER DEFAULT 0,
    profit_count INTEGER DEFAULT 0,
    
    -- Totals
    total_profit_puntos REAL DEFAULT 0,
    total_loss_puntos REAL DEFAULT 0,
    
    -- Metadata
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(strategy, symbol, timeframe)
);
```

---

## 🔄 Phase 1 Implementation

**Current Status**: Phase 1 already implements this correctly!

✅ **Phase 1 code reads ONE candle from MT5:**
```python
# backend/api_server.py
rates = mt5.copy_rates_from_pos(symbol, mt5_timeframe, 1, 1)
# Returns candle, NO storage
```

✅ **Phase 1 displays candle, does NOT store it**

✅ **Phase 1 has NO SQLite yet** (correct for validation phase)

---

## 📋 Phase 2 Implementation Plan

When implementing Phase 2, follow this pattern:

### 1. Engine Module (Pure Calculation)

```python
# engines/smc_engine.py
def analyze_m15(symbol: str) -> dict:
    """
    Pure SMC analysis - reads from MT5, processes in memory
    Returns results only, no persistence
    """
    # Read what we need from MT5
    m15_candles = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 1000)
    h1_candles = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 500)
    
    # Convert to DataFrames
    df_m15 = pd.DataFrame(m15_candles)
    df_h1 = pd.DataFrame(h1_candles)
    
    # Run analysis (all in memory)
    swings = detect_swings(df_m15)
    bos = detect_bos(swings)
    zones = create_zones(df_m15, bos)
    
    # Return results (not persisted yet)
    return {
        'zones': zones,
        'h1_trend': get_trend(df_h1),
        'm15_event': get_last_event(df_m15),
        # ... more results
    }
```

### 2. Persistence Module (Separate)

```python
# backend/persistence.py
def save_analysis_results(results: dict):
    """
    Save engine results to SQLite
    Separate from engine logic
    """
    for zone in results['zones']:
        # Save to smc_m15_setups
        db.insert_setup({
            'symbol': zone['symbol'],
            'zona_high': zone['high'],
            'zona_low': zone['low'],
            'h1_trend': results['h1_trend'],
            'm15_event': results['m15_event'],
            'estado': 'ACTIVA',
            # ... more fields
        })
```

### 3. Background Monitor (Event-Driven)

```python
# backend/monitor.py
async def monitor_symbols():
    """
    Background task: Monitor MT5 and process
    """
    while True:
        for symbol in SYMBOLS:
            # Check if new candle
            if has_new_candle(symbol):
                # Run engine (reads from MT5)
                results = smc_engine.analyze_m15(symbol)
                
                # Save results (NOT candles)
                persistence.save_analysis_results(results)
                
                # Emit event
                await emit_event('setup_updated', results)
        
        await asyncio.sleep(1)
```

---

## ✅ Summary

### Correct Understanding:

1. **Engine reads from MT5** ← Direct, as many candles as needed
2. **Process in memory** ← DataFrames, calculations, all in RAM
3. **Discard candles** ← After processing, no persistence
4. **Save RESULTS** ← Setups, states, TP/SL to SQLite
5. **History complete** ← Pre-calculated, no recalculation needed
6. **Optional buffer** ← Small, limited, for optimization only

### Wrong Understanding (Avoid):

❌ Store all candles in SQLite first, then read from there  
❌ History depends on recalculating from old candles  
❌ Engine depends on SQLite for data  
❌ Buffer is required for engine to work  

---

**Architecture Status**: ✅ Clarified and documented

This clarification ensures the desktop application is:
- **Efficient**: No unnecessary storage
- **Fast**: Direct MT5 access
- **Scalable**: History doesn't grow with candles
- **Clean**: Separation of concerns (read → process → persist results)
