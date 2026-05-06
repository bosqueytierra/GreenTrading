# GreenTrading Desktop - Architecture Documentation

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

### Limited Buffer Strategy

```python
class CandleBuffer:
    """
    Limited in-memory buffer for candles
    NO full database storage
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
    
    def get_candles(self, symbol, timeframe, count=None):
        """Get recent candles from buffer"""
        key = (symbol, timeframe)
        
        if key not in self.buffers:
            return []
        
        buffer = self.buffers[key]
        
        if count is None:
            return list(buffer)
        
        return list(buffer)[-count:]
    
    def clear_old(self):
        """Buffer automatically limits size (deque maxlen)"""
        pass  # No action needed, deque handles it
```

### Engine Independence

```python
# CORRECT: Engine doesn't depend on SQLite

def analyze_smc(candles: List[dict]) -> dict:
    """
    Pure SMC analysis - NO database dependency
    
    Input: List of candle dictionaries
    Output: Analysis results dictionary
    """
    # 1. Convert to DataFrame
    df = pd.DataFrame(candles)
    
    # 2. Run SMC logic (pure calculation)
    swings = detect_swings(df)
    bos = detect_bos(swings)
    choch = detect_choch(swings)
    fvg = detect_fvg(df)
    zones = detect_zones(df, bos, choch, fvg)
    
    # 3. Return results (NO database write here)
    return {
        'swings': swings,
        'bos': bos,
        'choch': choch,
        'fvg': fvg,
        'zones': zones
    }

# Then, separately, save results to SQLite
def save_analysis_results(results: dict):
    """
    Persist analysis results to SQLite
    Separate from engine logic
    """
    for zone in results['zones']:
        # Save setup to smc_m15_setups table
        db.insert_setup(zone)
```

## SQLite Usage (Minimal)

### What to Store

✅ **Store in SQLite:**
- Setups (zonas SMC detectadas)
- Setup history (estado, TP/SL)
- Metrics and statistics
- User preferences

❌ **DON'T Store in SQLite:**
- Raw market candles (too much data)
- Intermediate calculations
- Temporary analysis data

### Tables (Future)

```sql
-- Setups only (no market_candles table)
CREATE TABLE smc_m15_setups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    setup_time TIMESTAMP NOT NULL,
    estado TEXT NOT NULL,  -- ACTIVA, EN_ZONA, PROFIT, TP, SL
    zona_high REAL,
    zona_low REAL,
    entry_price REAL,
    tp_price REAL,
    sl_price REAL,
    resultado_puntos REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Similar tables for other strategies
-- smc_h1_m15_setups
-- smc_tendency_h1_m15_setups

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
- Add limited candle buffer (300-500 candles)
- Integrate SMC engines (in-memory processing)
- Add minimal SQLite (setups only)
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
