# GreenTrading Desktop - Architecture Documentation

> **📖 Important**: Read [ARCHITECTURE_CLARIFICATION.md](./ARCHITECTURE_CLARIFICATION.md) for detailed explanation of candle processing and storage strategy.

## Event-Driven Architecture (Future Phases)

### Current Implementation (Phase 1)
- Electron ↔ Python via HTTP REST
- Single request/response for ONE candle
- Proof of concept only

### Future Implementation (Phase 2+)

#### WebSocket Event Flow

```
┌──────────────┐                  ┌──────────────┐                  ┌──────────────┐
│   Electron   │                  │    Python    │                  │     MT5      │
│   Frontend   │                  │   Backend    │                  │              │
└──────┬───────┘                  └──────┬───────┘                  └──────┬───────┘
       │                                  │                                  │
       │  1. WebSocket Connect            │                                  │
       ├─────────────────────────────────>│                                  │
       │                                  │                                  │
       │  2. Subscribe to events          │                                  │
       ├─────────────────────────────────>│                                  │
       │                                  │                                  │
       │                                  │  3. Monitor MT5 (background)     │
       │                                  ├─────────────────────────────────>│
       │                                  │                                  │
       │                                  │  4. New candle detected          │
       │                                  │<─────────────────────────────────┤
       │                                  │                                  │
       │                                  │  5. Process in-memory            │
       │                                  │     (run SMC engine)             │
       │                                  │                                  │
       │  6. Emit event: new_candle       │                                  │
       │<─────────────────────────────────┤                                  │
       │                                  │                                  │
       │  7. Update UI (no polling!)      │                                  │
       │                                  │                                  │
```

#### Event Types (Future)

1. **candle_update**: New candle available
2. **setup_created**: New SMC setup detected
3. **setup_updated**: Setup state changed (EN_ZONA, PROFIT, TP, SL)
4. **zone_triggered**: Price entered zone
5. **status_changed**: MT5 connection status

#### Python Backend Events

```python
# Pseudo-code for future implementation

from fastapi import WebSocket
import asyncio

class EventManager:
    def __init__(self):
        self.subscribers = []
        self.candle_buffer = {}  # Limited buffer (300-500 candles)
        
    async def monitor_mt5(self):
        """Background task: Monitor MT5 for new candles"""
        while True:
            # Read new candles from MT5
            new_candles = await self.read_new_candles()
            
            if new_candles:
                # Process in-memory (NO database write for candles)
                results = self.process_candles(new_candles)
                
                # Save results to SQLite (setups only)
                await self.save_results(results)
                
                # Emit events to all subscribers
                await self.emit('candle_update', new_candles)
                await self.emit('setups_updated', results)
            
            await asyncio.sleep(1)  # Check every second
    
    def process_candles(self, candles):
        """Process candles in-memory with SMC engine"""
        # Flow: candles → engine → results
        # NO SQLite dependency in engine
        
        results = []
        for symbol_candles in candles:
            # Run SMC engine (pure calculation)
            analysis = smc_engine.analyze(symbol_candles)
            results.append(analysis)
        
        return results
    
    async def emit(self, event_type, data):
        """Emit event to all WebSocket subscribers"""
        for ws in self.subscribers:
            await ws.send_json({
                'event': event_type,
                'data': data
            })
```

#### Electron Frontend Events

```javascript
// Pseudo-code for future implementation

class EventClient {
    constructor() {
        this.ws = null;
        this.handlers = {};
    }
    
    connect() {
        this.ws = new WebSocket('ws://localhost:8765/ws');
        
        this.ws.onmessage = (event) => {
            const { event: eventType, data } = JSON.parse(event.data);
            
            // Dispatch to registered handlers
            if (this.handlers[eventType]) {
                this.handlers[eventType].forEach(handler => {
                    handler(data);
                });
            }
        };
    }
    
    on(eventType, handler) {
        if (!this.handlers[eventType]) {
            this.handlers[eventType] = [];
        }
        this.handlers[eventType].push(handler);
    }
    
    emit(eventType, data) {
        this.ws.send(JSON.stringify({
            event: eventType,
            data: data
        }));
    }
}

// Usage
const events = new EventClient();
events.connect();

// Listen for new candles
events.on('candle_update', (candles) => {
    console.log('New candles:', candles);
    updateDashboard(candles);
});

// Listen for new setups
events.on('setup_created', (setup) => {
    console.log('New setup:', setup);
    addSetupToTable(setup);
});

// Listen for setup updates
events.on('setup_updated', (setup) => {
    console.log('Setup updated:', setup);
    updateSetupInTable(setup);
});
```

## In-Memory Candle Processing

### Key Principle: Engine Reads from MT5

**IMPORTANT CLARIFICATION**: The engine reads candles DIRECTLY from MT5, not from SQLite.

```python
def analyze_smc(symbol: str) -> dict:
    """
    Engine reads from MT5 whatever it needs
    Process in memory, return results
    """
    # 1. Read candles directly from MT5 (as many as needed)
    m15_candles = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 1000)
    h1_candles = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 500)
    
    # 2. Convert to DataFrames (in memory)
    df_m15 = pd.DataFrame(m15_candles)
    df_h1 = pd.DataFrame(h1_candles)
    
    # 3. Run SMC analysis (all in memory)
    swings = detect_swings(df_m15)
    bos = detect_bos(swings)
    zones = detect_zones(df_m15, bos)
    
    # 4. Return results (candles discarded after this)
    return {
        'zones': zones,
        'h1_trend': get_trend(df_h1),
        'm15_event': get_last_event(df_m15)
    }

# Then save RESULTS (not candles) to SQLite
def save_analysis_results(results: dict):
    """
    Persist analysis results to SQLite
    Separate from engine logic
    """
    for zone in results['zones']:
        db.insert_setup(zone)  # Save setup, not candles
```

### Optional: Limited Buffer (For Optimization Only)

```python
class CandleBuffer:
    """
    OPTIONAL: Limited buffer for recent candles
    Purpose: Avoid repeated MT5 queries for recent data
    NOT required for engine to work
    """
    
    def __init__(self, max_candles=500):
        self.max_candles = max_candles
        self.buffers = {}  # {symbol: {timeframe: deque}}
    
    def add_candle(self, symbol, timeframe, candle):
        """Add candle to buffer (FIFO, limited size)"""
        key = (symbol, timeframe)
        
        if key not in self.buffers:
            self.buffers[key] = deque(maxlen=self.max_candles)
        
        self.buffers[key].append(candle)
    
    def get_or_fetch_from_mt5(self, symbol, timeframe, count):
        """
        Try buffer first, fetch from MT5 if needed
        """
        buffer = self.get_recent(symbol, timeframe, count)
        
        if len(buffer) < count:
            # Buffer miss - read from MT5
            return mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
        
        return buffer
```

## SQLite Usage (Minimal)

### What to Store

✅ **Store in SQLite:**
- **Setups** (zonas SMC detectadas) with ALL context at creation
- **Setup history** (estado changes, TP/SL hits, results)
- **Metrics and statistics** (TP/SL counts, profit/loss)
- **User preferences**
- **OPTIONAL**: Limited buffer of recent candles (300-500 max per symbol/timeframe)

❌ **DON'T Store in SQLite:**
- ❌ ALL historical candles (engine reads from MT5)
- ❌ Intermediate calculations
- ❌ Temporary analysis data

### Critical Point: History is Pre-Calculated

**History does NOT depend on recalculating old candles.**

When a setup is created, we store:
- Zone boundaries
- Context indicators (H1 trend, M15 event, etc.)
- Timestamps
- State transitions
- Final results (TP/SL)

When viewing history, we display stored results directly - NO recalculation needed.

**Example**: A setup from 2 weeks ago shows "TP: +8 points" because we stored that result when it happened. We don't need to re-read old candles to know this.

### Tables (Future)

```sql
-- Setups with complete pre-calculated context
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
    
    -- Context at creation (pre-calculated, stored once)
    h1_trend TEXT,           -- ALCISTA/BAJISTA
    m15_event TEXT,          -- BOS/CHOCH
    m15_trend TEXT,          -- ALCISTA/BAJISTA
    fvg_present BOOLEAN,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Similar tables for other strategies
-- smc_h1_m15_setups
-- smc_tendency_h1_m15_setups

-- OPTIONAL: Recent candles buffer (max 300-500 per symbol/timeframe)
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
    UNIQUE(symbol, timeframe, timestamp)
);
-- Note: Application enforces limit (keeps only last 500 per symbol/timeframe)

-- Metrics
CREATE TABLE metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy TEXT NOT NULL,
    symbol TEXT NOT NULL,
    tp_count INTEGER DEFAULT 0,
    sl_count INTEGER DEFAULT 0,
    profit_total REAL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Phase Roadmap

### ✅ Phase 1 (Current)
- Electron + Python + MT5 stack validation
- Read ONE candle via HTTP REST
- Display in UI
- NO events, NO database, NO strategies

### 🔄 Phase 2 (Next)
- Implement WebSocket events
- Engine reads candles directly from MT5 (as many as needed)
- Integrate SMC engines (in-memory processing)
- Add minimal SQLite (setups with pre-calculated context)
- OPTIONAL: Add limited candle buffer for optimization (300-500)
- Real-time updates without polling

### 📋 Phase 3 (Future)
- Full dashboard with all strategies
- History viewer with filters
- Statistics and metrics
- Performance monitoring

### 🚀 Phase 4 (Future)
- Packaging for Windows (.exe installer)
- Auto-update mechanism
- User preferences
- Export functionality

---

**Important**: Each phase MUST be validated before moving to the next.
Phase 1 is complete when you can successfully read and display ONE candle from MT5.
