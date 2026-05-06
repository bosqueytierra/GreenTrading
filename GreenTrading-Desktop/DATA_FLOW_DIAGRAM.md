# Data Flow Diagram - GreenTrading Desktop

**Visual representation of the architecture with clarifications**

---

## 🎯 Complete System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          ELECTRON FRONTEND                          │
│                                                                     │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐  │
│  │ Dashboard  │  │  History   │  │  Metrics   │  │ Settings   │  │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘  │
│         │                │                │                │        │
│         └────────────────┴────────────────┴────────────────┘        │
│                              │                                      │
│                    WebSocket Events (Phase 2+)                     │
│                              │                                      │
└──────────────────────────────┼──────────────────────────────────────┘
                               │
                               ↓
┌─────────────────────────────────────────────────────────────────────┐
│                        PYTHON BACKEND                               │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │              Background Monitor (Phase 2+)                  │  │
│  │  - Detects new candles every second                        │  │
│  │  - Triggers analysis                                       │  │
│  │  - Emits events                                            │  │
│  └────────────┬────────────────────────────────────────────────┘  │
│               │                                                     │
│               ↓                                                     │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                   SMC ENGINE                                │  │
│  │                                                             │  │
│  │  1. Read candles FROM MT5                                  │  │
│  │     ├─ M15: 1000 candles ──→ mt5.copy_rates_from_pos()    │  │
│  │     └─ H1: 500 candles ────→ mt5.copy_rates_from_pos()    │  │
│  │                                                             │  │
│  │  2. Process in MEMORY (NO SQLite dependency)               │  │
│  │     ├─ Convert to DataFrames                               │  │
│  │     ├─ Detect swings, BOS, CHOCH                          │  │
│  │     ├─ Identify FVG, zones                                 │  │
│  │     └─ Calculate TP/SL                                     │  │
│  │                                                             │  │
│  │  3. Return RESULTS (candles discarded)                     │  │
│  │     └─ Zones with context: {zona, h1_trend, m15_event}    │  │
│  │                                                             │  │
│  └────────────┬────────────────────────────────────────────────┘  │
│               │                                                     │
│               ↓                                                     │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                PERSISTENCE MODULE                           │  │
│  │                                                             │  │
│  │  Save RESULTS to SQLite:                                   │  │
│  │  ├─ New setups → INSERT with full context                 │  │
│  │  ├─ State changes → UPDATE estado                         │  │
│  │  ├─ TP/SL hits → UPDATE resultado_puntos                  │  │
│  │  └─ Metrics → UPDATE counters                             │  │
│  │                                                             │  │
│  └────────────┬────────────────────────────────────────────────┘  │
│               │                                                     │
└───────────────┼─────────────────────────────────────────────────────┘
                │
                ↓
┌─────────────────────────────────────────────────────────────────────┐
│                           STORAGE                                   │
│                                                                     │
│  ┌──────────────┐            ┌──────────────┐                     │
│  │   MT5 API    │            │   SQLite DB  │                     │
│  │              │            │              │                     │
│  │ ✅ Source    │            │ ✅ Results   │                     │
│  │ of candles   │            │ storage      │                     │
│  │              │            │              │                     │
│  │ - All        │            │ - Setups     │                     │
│  │   historical │            │ - States     │                     │
│  │   candles    │            │ - Results    │                     │
│  │ - Real-time  │            │ - Metrics    │                     │
│  │   data       │            │ - Optional:  │                     │
│  │              │            │   300-500    │                     │
│  │ READ FROM    │            │   buffer     │                     │
│  │ HERE ────┐   │            │              │                     │
│  │          │   │            │ WRITE TO     │                     │
│  │          │   │            │ HERE ──┐     │                     │
│  └──────────┼───┘            └────────┼─────┘                     │
│             │                         │                            │
└─────────────┼─────────────────────────┼────────────────────────────┘
              │                         │
              └─────────┬───────────────┘
                        │
                    ✅ CORRECT
                    Separate
                    Read from MT5
                    Write to SQLite


              ❌ INCORRECT (Don't do this)
              
              MT5 → SQLite → Engine
              (Storing all candles first)
```

---

## 📊 Data Types & Flow

### Type 1: Candles (Ephemeral)

```
Source: MT5
│
├─→ Read by Engine (on demand)
│   │
│   ├─ M15: 1000 candles
│   └─ H1: 500 candles
│
├─→ Process in Memory (DataFrames)
│
└─→ Discard after processing ✅
    
    Optional: Keep last 300-500 in buffer
              (optimization only)
```

### Type 2: Results (Persistent)

```
Created by: Engine processing
│
├─→ Setup detected
│   ├─ Zone boundaries (high, low)
│   ├─ Context at creation:
│   │   ├─ H1 trend: ALCISTA
│   │   ├─ M15 event: BOS
│   │   ├─ M15 trend: ALCISTA
│   │   └─ FVG present: true
│   ├─ Prices (entry, TP, SL)
│   └─ Timestamp
│
└─→ Save to SQLite ✅
    Never recalculated from candles
```

---

## 🔄 Processing Flow (Phase 2+)

### Real-Time Monitoring

```
Step 1: Background Task Running
┌────────────────────────────────────┐
│ while True:                        │
│   for symbol in SYMBOLS:           │
│     if new_candle_detected():      │
│       analyze(symbol) ────────┐    │
│   await sleep(1)              │    │
└───────────────────────────────┼────┘
                                │
                                ↓
Step 2: Engine Reads from MT5
┌───────────────────────────────────────┐
│ def analyze(symbol):                  │
│   # Direct MT5 read                   │
│   m15 = mt5.copy_rates_from_pos(      │
│       symbol, M15, 0, 1000            │
│   ) ──────────────────────────────┐   │
│   h1 = mt5.copy_rates_from_pos(   │   │
│       symbol, H1, 0, 500          │   │
│   ) ──────────────────────────────┘   │
└───────────────────────────────────────┘
                │
                ↓
Step 3: In-Memory Processing
┌───────────────────────────────────────┐
│ df_m15 = pd.DataFrame(m15)            │
│ df_h1 = pd.DataFrame(h1)              │
│                                       │
│ swings = detect_swings(df_m15)       │
│ bos = detect_bos(swings)              │
│ zones = create_zones(df_m15, bos)    │
│                                       │
│ # Candles in RAM, not persisted      │
└───────────────────────────────────────┘
                │
                ↓
Step 4: Save Results Only
┌───────────────────────────────────────┐
│ for zone in zones:                    │
│   db.insert_setup({                   │
│     'zona_high': zone.high,           │
│     'zona_low': zone.low,             │
│     'h1_trend': 'ALCISTA',  ← stored  │
│     'm15_event': 'BOS',     ← stored  │
│     'estado': 'ACTIVA',               │
│     ...                               │
│   })                                  │
│                                       │
│ # Candles discarded here             │
└───────────────────────────────────────┘
                │
                ↓
Step 5: Emit Event
┌───────────────────────────────────────┐
│ await emit_event('setup_created', {   │
│   'setup_id': 123,                    │
│   'symbol': 'Boom 1000 Index',        │
│   'zona_high': 12345.67,              │
│   ...                                 │
│ })                                    │
└───────────────────────────────────────┘
                │
                ↓
Step 6: UI Updates
┌───────────────────────────────────────┐
│ Dashboard receives event              │
│ → Adds new row to table               │
│ → No polling needed ✅                │
└───────────────────────────────────────┘
```

---

## 📋 History Display (No Recalculation)

### User Opens History Tab

```
User clicks "History"
        │
        ↓
Query SQLite
┌─────────────────────────────────────────┐
│ SELECT * FROM smc_m15_setups            │
│ WHERE estado IN ('TP', 'SL', 'PROFIT')  │
│ ORDER BY closed_at DESC                 │
│ LIMIT 100                               │
└────────────┬────────────────────────────┘
             │
             ↓
Display Results
┌─────────────────────────────────────────┐
│ Row 1: Boom 1000 | TP | +8.0 pts       │
│        H1: ALCISTA | M15: BOS           │
│        Created: 2026-04-20 10:00        │
│        Closed: 2026-04-20 12:30         │
│                                         │
│ Row 2: Crash 500 | SL | -5.2 pts       │
│        H1: BAJISTA | M15: CHOCH         │
│        Created: 2026-04-19 14:15        │
│        Closed: 2026-04-19 15:00         │
│                                         │
│ [All data from SQLite]                  │
│ [NO candle reading]                     │
│ [NO recalculation]                      │
└─────────────────────────────────────────┘
```

**Key Point**: Everything needed to display history is already stored:
- ✅ Zone boundaries
- ✅ Context indicators (H1 trend, M15 event)
- ✅ State transitions
- ✅ Final results
- ✅ Timestamps

**NO need to**:
- ❌ Read old candles from MT5
- ❌ Recalculate indicators
- ❌ Re-run SMC engine

---

## 💾 SQLite Tables (Phase 2+)

### Setup Table (Example)

```sql
CREATE TABLE smc_m15_setups (
    id INTEGER PRIMARY KEY,
    symbol TEXT,
    
    -- Zone definition
    zona_high REAL,
    zona_low REAL,
    
    -- Context (stored at creation, NEVER recalculated)
    h1_trend TEXT,      -- 'ALCISTA' or 'BAJISTA'
    m15_event TEXT,     -- 'BOS' or 'CHOCH'
    m15_trend TEXT,     -- 'ALCISTA' or 'BAJISTA'
    fvg_present BOOLEAN,
    
    -- State & Result
    estado TEXT,        -- 'ACTIVA', 'EN_ZONA', 'TP', 'SL', etc.
    resultado_puntos REAL,
    
    -- Timestamps
    setup_time TIMESTAMP,
    entry_time TIMESTAMP,
    closed_at TIMESTAMP
);
```

### Why This Works

1. **Context stored at creation** → Don't need candles to know H1 was ALCISTA
2. **Results stored when they happen** → Don't need to recalculate TP hit
3. **History is complete** → All info needed for display is there

---

## ✅ Summary

### Correct Flow ✅

```
MT5 ──Read──→ Engine ──Process──→ Results ──Save──→ SQLite
   (source)   (memory)  (discard)   (persist)
```

### Incorrect Flow ❌

```
MT5 ──Save──→ SQLite ──Read──→ Engine
   (source)   (all candles)   (slow, bloated)
```

---

## 🎯 Key Takeaways

1. **Engine is independent** - Reads from MT5, no SQLite dependency
2. **Candles are ephemeral** - Read, process, discard
3. **Results are persistent** - Complete context stored once
4. **History never recalculates** - Display pre-calculated data
5. **Optional buffer** - Small, for optimization only
6. **Event-driven** - Real-time updates, no polling

---

**Diagram Status**: ✅ Complete visual representation of clarified architecture

This diagram should be used as reference when implementing Phase 2+.
