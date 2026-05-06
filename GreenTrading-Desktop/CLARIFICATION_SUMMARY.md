# Phase 1 - Final Architecture Clarification Summary

**Date**: 2026-05-06  
**Status**: ✅ Complete and Clarified

---

## 🎯 What Changed

### Original Implementation (Phase 1)
✅ Already correct - reads ONE candle from MT5, displays it, NO storage

### Clarification Added
📖 Documented how Phase 2+ will work with the correct data flow

---

## 📋 Key Points Clarified

### 1. Engine Reads Directly from MT5

**✅ CORRECT Flow:**
```
MT5 ←──── Engine reads candles ──── Process in memory ──── Results ────→ SQLite
         (as many as needed)       (DataFrames, calcs)   (setups only)
```

**Example:**
```python
# Phase 2+ implementation
def analyze_symbol(symbol):
    # Engine reads from MT5 (no intermediate storage)
    m15_candles = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 1000)
    h1_candles = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 500)
    
    # Process in memory
    results = smc_engine.analyze(m15_candles, h1_candles)
    
    # Save RESULTS (not candles) to SQLite
    save_setups(results)
```

### 2. SQLite Storage Strategy

#### ✅ Store in SQLite:

1. **Setups with complete pre-calculated context**
   - Zone boundaries
   - H1 trend at creation
   - M15 event at creation
   - Entry/TP/SL prices
   - Timestamps

2. **State history**
   - ACTIVA → EN_ZONA → TP/SL
   - Results (profit/loss in points)
   - Close reasons

3. **Metrics**
   - TP/SL counts per symbol/strategy
   - Total profit/loss

4. **OPTIONAL: Limited candle buffer**
   - Last 300-500 candles per symbol/timeframe
   - For optimization only (avoid repeated MT5 queries)
   - NOT required for engine to work

#### ❌ DON'T Store in SQLite:

- ❌ All historical candles (engine reads from MT5)
- ❌ Intermediate calculations
- ❌ Temporary data

### 3. History Does NOT Recalculate

**Critical Point**: History is pre-calculated and stored.

When viewing history, we display:
- Stored setup data (created 2 weeks ago)
- Stored state transitions (when it went EN_ZONA)
- Stored results (TP: +8 points)

**NO need to**:
- Re-read old candles
- Recalculate indicators
- Re-run engine on past data

**Example History Record:**
```json
{
  "id": 123,
  "symbol": "Boom 1000 Index",
  "setup_time": "2026-04-20T10:00:00Z",
  "zona_high": 12345.67,
  "zona_low": 12340.50,
  "estado": "TP",
  "resultado_puntos": 8.0,
  "h1_trend": "ALCISTA",      // Stored at creation
  "m15_event": "BOS",          // Stored at creation
  "closed_at": "2026-04-20T12:30:00Z"
}
```

This record is complete. Display it directly. No recalculation needed.

---

## 📚 Documentation Structure

### Main Documents

1. **[README.md](./README.md)**
   - Quick start guide
   - Installation instructions
   - Phase 1 objectives
   - Links to detailed docs

2. **[ARCHITECTURE.md](./ARCHITECTURE.md)**
   - Event-driven architecture (Phase 2+)
   - Code examples
   - Phase roadmap

3. **[ARCHITECTURE_CLARIFICATION.md](./ARCHITECTURE_CLARIFICATION.md)** ⭐ NEW
   - **Detailed explanation of data flow**
   - Engine reads from MT5 (not SQLite)
   - History storage strategy
   - SQLite schema with context
   - Complete examples

4. **[SECURITY.md](./SECURITY.md)**
   - Security audit
   - Vulnerability fixes
   - Best practices

5. **[PHASE1_SUMMARY.md](./PHASE1_SUMMARY.md)**
   - Phase 1 completion status
   - What was implemented
   - Testing checklist

---

## 🔍 Key Architectural Decisions

### Decision 1: Engine Independence
- ✅ Engine reads from MT5 directly
- ✅ Engine has NO SQLite dependency
- ✅ Results flow to SQLite separately

**Why**: Separation of concerns, testability, flexibility

### Decision 2: Pre-Calculated History
- ✅ Store complete context at setup creation
- ✅ Store state transitions as they happen
- ✅ Never recalculate from old candles

**Why**: Performance, reliability, simplicity

### Decision 3: Optional Buffer
- ✅ Small buffer for recent candles (optimization)
- ✅ NOT required for engine
- ✅ Auto-managed (FIFO, size limit)

**Why**: Reduce MT5 queries without bloating database

### Decision 4: Event-Driven Updates
- ✅ Python monitors MT5, emits events
- ✅ Electron listens via WebSocket
- ❌ NO polling with setInterval

**Why**: Real-time, efficient, scalable

---

## 🎓 Understanding the Flow

### Real-Time Processing (Phase 2+)

```
1. Background Monitor
   ↓
2. Detect new candle in MT5
   ↓
3. Engine reads candles from MT5
   (M15: 1000 candles, H1: 500 candles)
   ↓
4. Process in memory
   (Detect zones, calculate TP/SL, etc.)
   ↓
5. Save RESULTS to SQLite
   (New setup with full context)
   ↓
6. Emit event to Electron
   (WebSocket: "setup_created")
   ↓
7. UI updates
   (Dashboard shows new setup)
```

### Viewing History

```
1. User clicks "History" tab
   ↓
2. Query SQLite
   SELECT * FROM smc_m15_setups
   WHERE estado IN ('TP', 'SL')
   ORDER BY closed_at DESC
   ↓
3. Display results
   (All data already calculated and stored)
   ↓
NO candle reading
NO recalculation
Just display stored data ✅
```

---

## ✅ Verification Checklist

- [x] Phase 1 code reads from MT5 (not SQLite) ✅
- [x] Phase 1 does NOT store candles ✅
- [x] Documentation explains engine reads from MT5 ✅
- [x] Documentation explains history is pre-calculated ✅
- [x] SQLite schema includes context fields ✅
- [x] Optional buffer strategy documented ✅
- [x] Event-driven architecture documented ✅
- [x] All clarifications reflected in README ✅
- [x] All clarifications reflected in ARCHITECTURE.md ✅
- [x] Comprehensive ARCHITECTURE_CLARIFICATION.md created ✅

---

## 🚀 Ready for Phase 2

With this clarification:

1. ✅ Architecture is clearly defined
2. ✅ Data flow is documented
3. ✅ Storage strategy is explicit
4. ✅ No ambiguity about candle handling
5. ✅ History strategy is clear

**Next steps** (Phase 2):
1. Test Phase 1 on Windows with MT5
2. Validate stack works correctly
3. Implement Phase 2 following clarified architecture
4. Engine reads from MT5 ✅
5. Results saved to SQLite ✅
6. History pre-calculated ✅

---

## 📞 Quick Reference

**Q: Where does the engine read candles from?**  
A: Directly from MT5 via `mt5.copy_rates_from_pos()`

**Q: How many candles can it read?**  
A: As many as needed for correct analysis (e.g., 500-1000+)

**Q: Are candles stored in SQLite?**  
A: No, only optionally a small buffer (300-500 recent) for optimization

**Q: What is stored in SQLite?**  
A: Setups with full pre-calculated context, states, results, metrics

**Q: Does history need candles to display?**  
A: No, history is pre-calculated and stored complete

**Q: What happens when price changes?**  
A: Engine re-reads from MT5, processes fresh data, updates states in SQLite

---

**Status**: ✅ Architecture clarified and documented

All documents updated. Phase 1 ready for testing. Phase 2 architecture fully defined.
