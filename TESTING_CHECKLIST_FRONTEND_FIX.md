# Testing Checklist: Frontend Mapping Fix

## Pre-Testing Setup

### 1. Start the Backend (Port 8000)
```bash
cd /path/to/GreenTrading/GreenTrading-Desktop/backend
python3 api_server.py
```

**Expected Output:**
```
Initializing MT5 connection...
MT5 connected: [Terminal Name]
Uvicorn running on http://127.0.0.1:8000
```

### 2. Verify Backend is Working
```bash
curl http://127.0.0.1:8000/api/smc/m15-pro/snapshot | jq
```

**Expected Response Structure:**
```json
[
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
  },
  // ... 9 more symbols
]
```

## Running the Electron App

### 3. Install Dependencies (if needed)
```bash
cd /path/to/GreenTrading/GreenTrading-Desktop
npm install
```

### 4. Start Electron
```bash
npm start
```

**Expected Behavior:**
- Electron window opens
- Dashboard loads
- NO Python backend is spawned (check console - should see "Skipping Python backend start")
- Frontend connects to existing backend on port 8000

## Visual Verification Checklist

### Boom Indices Table
For each Boom index (1000, 900, 600, 500, 300):

- [ ] **Symbol column** shows "Boom XXX" (without "Index")
- [ ] **Tendencia H1** shows:
  - ✅ "ALCISTA" or "BAJISTA" (NOT "--")
  - ✅ Styled with appropriate CSS class
- [ ] **Tendencia M15** shows:
  - ✅ "ALCISTA" or "BAJISTA" (NOT "--")
  - ✅ Styled with appropriate CSS class
- [ ] **Último Evento M15** shows:
  - ✅ "BOS-ALCISTA", "CHOCH-ALCISTA", "BOS-BAJISTA", "CHOCH-BAJISTA", or "--"
  - ✅ NOT "SIN SETUP" in this column
- [ ] **Zona Madre M15** shows:
  - ✅ "12300.00 - 12320.00" format (when zone exists)
  - ✅ "--" (when no zone)
  - ✅ NOT "0 - 0"
- [ ] **Score** shows:
  - ✅ Number between 0-10
  - ✅ Color-coded: green (7-10), orange (4-6), red (0-3)
  - ✅ NOT always 0
- [ ] **OB, FVG, Barrida** columns show:
  - ✅ "SÍ" or "NO" (NOT placeholder text)
- [ ] **Estado** shows:
  - ✅ "✓ ACTIVA" with green badge (when score > 0)
  - ✅ "○ SIN SETUP" with gray badge (when score = 0)
- [ ] **Precio** shows:
  - ✅ Current price (e.g., "12345.67")
  - ✅ NOT "--"
- [ ] **Actualización** shows:
  - ✅ Time in HH:MM:SS format
  - ✅ Updates every 5 seconds

### Crash Indices Table
Repeat same checks for Crash indices (1000, 900, 600, 500, 300)

### Connection Status
- [ ] Top-right corner shows:
  - ✅ Green dot
  - ✅ "MT5: Conectado"

### Auto-Refresh
- [ ] Data updates automatically every 5 seconds
- [ ] "Última actualización" timestamp updates
- [ ] Console shows "⏰ Auto-refresh triggered" every 5 seconds

## Console Debugging

Open DevTools (Ctrl+Shift+I or Cmd+Option+I) and check Console tab:

### Initial Load
Expected logs in order:
```
✅ Dashboard script loaded
🚀 Initializing GreenTrading Desktop Dashboard...
📊 Loading SMC M15 PRO dashboard data...
Fetching SMC M15 PRO snapshot from: http://localhost:8000/api/smc/m15-pro/snapshot
DEBUG main.js - Raw backend response: [Array of 10 objects]
✅ Loaded 10 SMC snapshots
DEBUG loadDashboardData - Raw API response: [Array of 10 objects]
DEBUG createTableRow - Snapshot received: {object}  (x10 times, once per symbol)
DEBUG formatZone - Input: {desde: X, hasta: Y}  (x10 times)
DEBUG formatEstadoBadge - Input: "ACTIVA" or "SIN SETUP"  (x10 times)
DEBUG formatScoreBadge - Input: [number]  (x10 times)
✅ Dashboard initialized
✅ Auto-refresh started (every 5s)
```

### Check for Errors
- [ ] ❌ NO "HTTP 404" errors
- [ ] ❌ NO "Failed to fetch" errors
- [ ] ❌ NO "undefined property" errors
- [ ] ❌ NO CORS errors

## Data Validation

### Sample Valid ACTIVA Zone
When estado = "ACTIVA", verify:
- [ ] tendencia_h1 is NOT "--"
- [ ] tendencia_m15 is NOT "--"
- [ ] ultimo_evento_m15 is NOT "--"
- [ ] zona_madre_m15 is NOT "0 - 0"
- [ ] score is > 0
- [ ] Row has green/highlighted styling

### Sample SIN SETUP
When estado = "SIN SETUP", verify:
- [ ] tendencia_h1 might be "--" or valid trend
- [ ] tendencia_m15 might be "--" or valid trend
- [ ] ultimo_evento_m15 is "--"
- [ ] zona_madre_m15 is "--"
- [ ] score is 0
- [ ] ob, fvg, barrida are "NO"
- [ ] Row has default/gray styling

## Common Issues and Solutions

### Issue: All rows show "SIN SETUP" with score 0
**Possible Causes:**
1. Backend not running on port 8000
2. MT5 not connected
3. Backend returning placeholder data

**Solution:**
- Check backend console for errors
- Verify MT5 connection
- Check backend logs for SMC analysis

### Issue: Some columns show "undefined"
**Possible Cause:** Property name mismatch

**Solution:**
- Check console logs for actual property names in response
- Verify backend is returning snake_case properties

### Issue: "Failed to fetch" error
**Possible Causes:**
1. Backend not running
2. Port mismatch
3. CORS issue

**Solution:**
- Restart backend
- Verify port 8000 is correct
- Check CORS configuration in backend

## Success Criteria

✅ **All 10 symbols display:**
- Valid trend indicators (not "--" for ACTIVA zones)
- Correct M15 events
- Zone ranges when applicable
- Scores > 0 for ACTIVA zones
- Proper indicator values (SÍ/NO)
- ACTIVA or SIN SETUP estado
- Current prices
- Auto-refreshing timestamps

✅ **No errors in console**

✅ **Auto-refresh works every 5 seconds**

✅ **Connection status shows "MT5: Conectado" with green dot**

## Cleanup After Successful Testing

Once verified working, remove debug logs from:

### `GreenTrading-Desktop/main.js`
Remove line ~191:
```javascript
console.log('DEBUG main.js - Raw backend response:', JSON.stringify(data, null, 2));
```

### `GreenTrading-Desktop/frontend/assets/js/dashboard.js`
Remove:
- Line ~58: `console.log('DEBUG loadDashboardData - Raw API response:', ...)`
- Line ~112: `console.log('DEBUG createTableRow - Snapshot received:', ...)`
- Line ~173-177: All `console.log` in `formatZone()`
- Line ~184: `console.log('DEBUG formatEstadoBadge - Input:', ...)`
- Line ~192: `console.log('DEBUG formatScoreBadge - Input:', ...)`

Then commit cleanup:
```bash
git add .
git commit -m "Remove debug logging after successful verification"
git push
```
