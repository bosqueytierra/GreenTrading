# FASE 3 - Testing and Validation Guide

## Summary
Phase 3 implementation complete. Dashboard now shows SMC M15 PRO analysis with:
- 5-second auto-refresh (changed from 10s)
- New SMC columns matching GreenTrading SMC M15 PRO format
- Real MT5 data integration with SMC engine analysis
- Proper handling of SIN SETUP when analysis not ready

## Testing Checklist

### Backend Testing
- [x] SMC service module imports correctly
- [x] Response structure matches expected format
- [x] Pandas dependency added
- [x] API endpoint structure verified

### Frontend Testing  
- [x] Auto-refresh interval changed to 5 seconds
- [x] Badge shows "Auto-refresh: 5s"
- [x] Table columns updated to SMC format (12 columns)
- [x] Boom and Crash tables separated
- [x] CSS styling for SMC badges and indicators
- [x] JavaScript functions rewritten for SMC rendering

### Integration Testing (Requires MT5)
- [ ] Backend starts without errors
- [ ] MT5 connection established
- [ ] 10 indices visible with real prices
- [ ] SMC analysis runs for all symbols
- [ ] Dashboard refreshes every 5 seconds
- [ ] No console errors in Electron DevTools
- [ ] Estado shows ACTIVA or SIN SETUP
- [ ] Scores calculated correctly
- [ ] Zones display properly
- [ ] Trends show from H1 and M15

## Running the Application

### 1. Install Dependencies
```bash
cd GreenTrading-Desktop
pip install -r requirements.txt
npm install
```

### 2. Ensure MT5 is Running
- MetaTrader 5 must be open and logged in
- Volatility indices (Boom/Crash) must be visible in Market Watch

### 3. Start the Application
```bash
npm start
```

### 4. Verify Dashboard
- Check that Python backend starts (console shows "Uvicorn running")
- Electron window opens with dashboard
- Connection status shows "MT5: Conectado"
- Both Boom and Crash tables load with 5 rows each
- Prices update in real-time

## Expected Behavior

### States
- **ACTIVA**: Zone with valid SMC setup (score > 0)
- **SIN SETUP**: No valid setup found or analysis incomplete

### Columns
1. **ÍNDICE**: Symbol short name (e.g., "Boom 1000")
2. **TENDENCIA H1**: H1 trend (ALCISTA/BAJISTA/--)
3. **TENDENCIA M15**: M15 trend (ALCISTA/BAJISTA/--)
4. **ÚLTIMO EVENTO M15**: Last structure event (BOS/CHOCH ALCISTA/BAJISTA)
5. **ZONA MADRE M15**: Zone range (from - to)
6. **SCORE**: Numeric score 0-10 with color coding
7. **OB**: Order block present (SÍ/NO)
8. **FVG**: Fair value gap present (SÍ/NO)
9. **BARRIDA**: Liquidity sweep detected (SÍ/NO)
10. **ESTADO**: Setup state (ACTIVA/SIN SETUP)
11. **PRECIO**: Current price from MT5
12. **ACTUALIZACIÓN**: Last update timestamp

### Score Color Coding
- **Green (7-10)**: High-quality setup
- **Yellow (4-6)**: Medium-quality setup
- **Gray (0-3)**: Low-quality or no setup

## Troubleshooting

### Backend Issues
- **Import errors**: Run `pip install -r requirements.txt`
- **MT5 not found**: Install MetaTrader5 Python package
- **Pandas not found**: Run `pip install pandas`
- **SMC engine not found**: Verify `src/smc_engine.py` exists in parent directory

### Frontend Issues
- **Blank dashboard**: Check browser DevTools console for errors
- **Connection failed**: Ensure backend is running on port 8765
- **No data**: Verify MT5 is running and symbols are in Market Watch

### Performance Issues
- **Slow refresh**: Analyzing 10 symbols with 100 candles each takes ~2-3 seconds
- **High CPU**: This is expected during SMC analysis, consider reducing candle count if needed

## What's NOT Implemented Yet
As per Phase 3 requirements:
- ❌ No database (SQLite/Supabase)
- ❌ No historical data storage
- ❌ No TP/SL tracking
- ❌ No multiple strategies selection
- ❌ No advanced estados (EN_ZONA, PROFIT, PAUSADA, TP, SL, DESCARTADA)
- ❌ Only ACTIVA and SIN SETUP states for now

## Next Phase Requirements
Phase 4 would include:
- SQLite for storing setups and history
- State transitions (ACTIVA → EN_ZONA → TP/SL)
- Historical tracking and metrics
- TP/SL configuration
- Multiple strategy support

## Code Structure

### Backend Files
- `backend/api_server.py`: FastAPI server with endpoints
- `backend/smc_m15_service.py`: SMC analysis service
- `src/smc_engine.py`: Core SMC detection logic (reused from web version)

### Frontend Files
- `frontend/pages/dashboard.html`: Dashboard HTML with SMC columns
- `frontend/assets/js/dashboard.js`: Dashboard logic with SMC rendering
- `frontend/assets/css/dashboard.css`: Styling including SMC badges
- `preload.js`: Electron IPC bridge exposing API
- `main.js`: Electron main process with IPC handlers

## Architecture Notes
- **NO database**: All analysis done in-memory from MT5 data
- **NO history**: Each refresh reads fresh candles from MT5
- **Engine reads directly from MT5**: Not from SQLite cache
- **Stateless**: No session persistence between restarts
