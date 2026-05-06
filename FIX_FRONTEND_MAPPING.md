# Fix: Frontend Property Mapping Issue

## Problem Summary
The backend API at `http://127.0.0.1:8000/api/smc/m15-pro/snapshot` was working correctly and returning valid SMC M15 PRO analysis data, but the Electron frontend was showing:
- `--` for trends and events
- Score: 0
- Estado: SIN SETUP

## Root Cause
The Electron application (GreenTrading-Desktop) was configured to:
1. Start its own Python backend on port **8765**
2. Connect to that backend on port 8765

However, the working, validated backend was running on port **8000**.

This caused the frontend to connect to the wrong backend (port 8765), which may not have been properly initialized or configured, resulting in incorrect or missing data.

## Solution Applied

### 1. Port Configuration Change
- **Changed port from 8765 to 8000** in both:
  - `GreenTrading-Desktop/main.js` (line 19)
  - `GreenTrading-Desktop/backend/api_server.py` (line 475)

### 2. Backend Connection Strategy
- **Disabled Electron from starting its own Python backend**
- Frontend now connects directly to the external working backend on port 8000
- Modified `main.js` to skip `startPythonBackend()` call (line 205)

### 3. Enhanced Debugging
Added comprehensive logging to track data flow:
- Backend response logging in `main.js` IPC handler
- Raw API response logging in `dashboard.js` loadDashboardData()
- Snapshot logging in `dashboard.js` createTableRow()
- Format function logging in `dashboard.js` (formatZone, formatEstadoBadge, formatScoreBadge)

### 4. Defensive Coding
Added default values in destructuring to handle missing properties gracefully:
```javascript
const {
    symbol = 'Unknown',
    price = null,
    tendencia_h1 = '--',
    tendencia_m15 = '--',
    ultimo_evento_m15 = '--',
    zona_madre_m15 = { desde: 0, hasta: 0 },
    score = 0,
    ob = 'NO',
    fvg = 'NO',
    barrida = 'NO',
    estado = 'SIN SETUP',
    updated_at = new Date().toISOString()
} = snapshot || {};
```

## Property Mapping Verification

The backend returns (snake_case):
```json
{
  "symbol": "Boom 1000 Index",
  "price": 12345.67,
  "tendencia_h1": "ALCISTA",
  "tendencia_m15": "ALCISTA",
  "ultimo_evento_m15": "BOS-ALCISTA",
  "zona_madre_m15": {
    "desde": 12300.00,
    "hasta": 12320.00
  },
  "score": 7,
  "ob": "SÍ",
  "fvg": "SÍ",
  "barrida": "NO",
  "estado": "ACTIVA",
  "updated_at": "2026-05-06T06:00:00Z"
}
```

The frontend correctly uses these exact property names (snake_case):
- ✅ `tendencia_h1`
- ✅ `tendencia_m15`
- ✅ `ultimo_evento_m15`
- ✅ `zona_madre_m15.desde` / `zona_madre_m15.hasta`
- ✅ `score`
- ✅ `ob`, `fvg`, `barrida`
- ✅ `estado`
- ✅ `price`
- ✅ `updated_at`

No camelCase conversion needed - property names match exactly.

## Testing Instructions

### Prerequisites
1. Ensure the working backend is running on port 8000:
   ```bash
   cd /home/runner/work/GreenTrading/GreenTrading/GreenTrading-Desktop/backend
   python3 api_server.py
   ```

2. Verify backend is responding:
   ```bash
   curl http://127.0.0.1:8000/api/smc/m15-pro/snapshot
   ```
   Should return JSON array with 10 symbols.

### Run Electron App
```bash
cd /home/runner/work/GreenTrading/GreenTrading/GreenTrading-Desktop
npm start
```

### Expected Results
The dashboard should now display:
- ✅ Correct trend indicators (ALCISTA/BAJISTA) instead of `--`
- ✅ M15 events (BOS-ALCISTA, CHOCH-BAJISTA, etc.) instead of `--`
- ✅ Zone ranges (e.g., "12300.00 - 12320.00") instead of `--`
- ✅ Actual scores (1-10) instead of 0
- ✅ Indicator values (SÍ/NO) instead of placeholder values
- ✅ Estado: ACTIVA when zone exists, SIN SETUP when no valid zone

### Debugging
Check browser console (Ctrl+Shift+I in Electron) for:
1. `DEBUG main.js - Raw backend response:` - Shows data from API
2. `DEBUG loadDashboardData - Raw API response:` - Shows data received by frontend
3. `DEBUG createTableRow - Snapshot received:` - Shows data for each row
4. Format function logs showing transformation of each field

### Cleanup After Testing
Once verified working, remove debug console.log statements from:
- `GreenTrading-Desktop/main.js` (line 191)
- `GreenTrading-Desktop/frontend/assets/js/dashboard.js` (lines ~58, ~112, ~173, ~184, ~192)

## Files Modified
1. `GreenTrading-Desktop/main.js`
   - Changed port from 8765 to 8000
   - Disabled Python backend spawning
   - Added debug logging in IPC handler

2. `GreenTrading-Desktop/backend/api_server.py`
   - Changed port from 8765 to 8000

3. `GreenTrading-Desktop/frontend/assets/js/dashboard.js`
   - Added comprehensive debug logging
   - Added defensive default values in destructuring
   - Enhanced formatZone() with better validation

## Backend Not Touched
As per requirements:
- ✅ No changes to backend logic
- ✅ No changes to SMC analysis
- ✅ No changes to MT5 connection
- ✅ No changes to endpoint structure

The backend was already working correctly - this was purely a frontend connectivity and configuration issue.
