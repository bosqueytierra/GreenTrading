# Phase 2 - Testing Checklist

## Pre-Test Requirements

Before running the application, ensure:

- [ ] **MetaTrader 5 is running**
- [ ] **MT5 is logged into an account**
- [ ] **Account has access to Boom/Crash indices**
- [ ] **Python dependencies installed**: `pip install -r requirements.txt`
- [ ] **Node dependencies installed**: `npm install`

## Running the Application

```bash
cd GreenTrading-Desktop
npm start
```

## Visual Verification

### 1. Application Launch
- [ ] Electron window opens without errors
- [ ] Window is approximately 1200x800 pixels
- [ ] Window title is "GreenTrading Desktop - Dashboard"

### 2. Backend Startup
- [ ] Python console shows "Starting GreenTrading Desktop API..."
- [ ] Python console shows "Uvicorn running on http://127.0.0.1:8765"
- [ ] Python console shows "MT5 connected" or similar success message
- [ ] No Python errors in console

### 3. Dashboard UI
- [ ] **Sidebar visible** on the left
  - [ ] GreenTrading logo displays
  - [ ] "Dashboard en vivo" link is active (green background)
  - [ ] "Configuración" link is visible
  
- [ ] **Header displays correctly**
  - [ ] Title: "Dashboard en vivo"
  - [ ] Connection status indicator on the right
  - [ ] Status shows "MT5: Conectado" with green pulsing dot
  
- [ ] **Controls bar displays**
  - [ ] "🔄 Actualizar" button visible
  - [ ] "Última actualización: HH:MM:SS" shows current time
  - [ ] "Auto-refresh: 10s" badge visible

### 4. Boom Indices Table
- [ ] Section title: "📈 Índices Boom" (green color)
- [ ] Table has 7 columns: Símbolo, Precio Actual, M1, M15, H1, Estado MT5, Actualizado
- [ ] Table shows exactly 5 rows:
  - [ ] Boom 1000 Index
  - [ ] Boom 900 Index
  - [ ] Boom 600 Index
  - [ ] Boom 500 Index
  - [ ] Boom 300 Index

### 5. Crash Indices Table
- [ ] Section title: "📉 Índices Crash" (red color)
- [ ] Table has 7 columns (same as Boom)
- [ ] Table shows exactly 5 rows:
  - [ ] Crash 1000 Index
  - [ ] Crash 900 Index
  - [ ] Crash 600 Index
  - [ ] Crash 500 Index
  - [ ] Crash 300 Index

### 6. Data Verification
For each row in both tables:
- [ ] **Símbolo**: Shows full index name
- [ ] **Precio Actual**: Shows a number (e.g., 1234.56) in monospace font
- [ ] **M1 (Close)**: Shows close price + time (e.g., "1234.56" with "14:30" below)
- [ ] **M15 (Close)**: Shows close price + time
- [ ] **H1 (Close)**: Shows close price + time
- [ ] **Estado MT5**: Shows green badge "✓ Conectado"
- [ ] **Actualizado**: Shows time in HH:MM:SS format

### 7. Real MT5 Data Verification
- [ ] **Prices are realistic** (not 0.00, not null, not "NaN")
- [ ] **Prices match MT5**: Open MT5 and compare a few prices manually
- [ ] **Times are recent**: Candle times should be within the last hour (or day for H1)
- [ ] **M1 time is most recent**: M1 time should be within last few minutes
- [ ] **M15 time is aligned**: M15 time should be on 15-minute boundaries (e.g., 14:15, 14:30, 14:45)
- [ ] **H1 time is aligned**: H1 time should be on hour boundaries (e.g., 14:00, 15:00)

### 8. Functionality Testing

#### Manual Refresh
- [ ] Click "🔄 Actualizar" button
- [ ] Tables show loading state (optional)
- [ ] Data updates
- [ ] "Última actualización" timestamp changes
- [ ] New timestamp is current time

#### Auto-Refresh
- [ ] Wait 10 seconds without clicking anything
- [ ] Data automatically updates
- [ ] "Última actualización" timestamp changes
- [ ] Connection status remains "Conectado"
- [ ] No errors in console

#### Hover Effects
- [ ] Hover over table rows
- [ ] Row background changes to light gray
- [ ] Cursor changes to default

#### Responsive Behavior
- [ ] Resize window to smaller size
- [ ] Tables remain readable
- [ ] Scroll appears if needed
- [ ] Layout doesn't break

### 9. Error Handling

#### MT5 Disconnection Test (optional)
- [ ] Close MT5 terminal
- [ ] Click refresh or wait for auto-refresh
- [ ] Connection status changes to "MT5: Desconectado" with red indicator
- [ ] Tables may show "--" or error state

#### Network Error Test (optional)
- [ ] Stop Python backend (Ctrl+C in terminal)
- [ ] Click refresh
- [ ] Console shows error message
- [ ] UI doesn't crash

### 10. Console Verification

#### Browser Console (Press F12 or Ctrl+Shift+I)
- [ ] No JavaScript errors
- [ ] Console shows: "✅ Dashboard script loaded"
- [ ] Console shows: "🚀 Initializing GreenTrading Desktop Dashboard..."
- [ ] Console shows: "✅ Dashboard initialized"
- [ ] Console shows: "📊 Loading dashboard data..."
- [ ] Console shows: "✅ Loaded 10 symbol snapshots"
- [ ] Every 10 seconds: "⏰ Auto-refresh triggered"

#### Python Console
- [ ] No Python errors
- [ ] Shows: "Reading snapshot for all dashboard symbols..."
- [ ] Shows: "Snapshot complete: 10 symbols read"
- [ ] Shows: "Reading candle: Boom 1000 Index @ M1"
- [ ] (Repeats for all symbols and timeframes)

## Performance Check

- [ ] **Initial load**: Data appears within 3-5 seconds
- [ ] **Refresh speed**: Manual refresh completes within 3-5 seconds
- [ ] **Auto-refresh smooth**: No UI freezing during auto-refresh
- [ ] **No memory leaks**: Application remains stable after 5+ minutes

## Known Limitations (Expected)

These are **NOT bugs** - they are intentional Phase 2 limitations:

- ⚠️ No historical data
- ⚠️ No SMC strategy indicators
- ⚠️ No database storage
- ⚠️ No WebSocket (uses polling)
- ⚠️ Settings page is placeholder (not functional)
- ⚠️ No error toast notifications (errors only in console)
- ⚠️ All 10 symbols refresh together (can be slow if MT5 is busy)
- ⚠️ No individual symbol selection
- ⚠️ No customizable refresh interval
- ⚠️ No dark mode

## Success Criteria

**Phase 2 is successful if:**

✅ All visual verification items pass
✅ Real MT5 data displays correctly
✅ Manual refresh works
✅ Auto-refresh works every 10 seconds
✅ No errors in console (browser or Python)
✅ Connection status updates correctly
✅ Application remains stable for 5+ minutes

## If Something Fails

1. **Check MT5 is running and logged in**
2. **Verify symbol names match your MT5 broker** (some brokers use different names)
3. **Check browser console for errors** (F12)
4. **Check Python console for errors**
5. **Verify Python dependencies installed**: `pip list | grep -E "fastapi|uvicorn|MetaTrader5"`
6. **Verify Node dependencies installed**: `ls node_modules | grep electron`
7. **Try restarting the application**: Close window, `npm start` again
8. **Check [PHASE2_IMPLEMENTATION.md](./PHASE2_IMPLEMENTATION.md) Troubleshooting section**

## Reporting Issues

If you find bugs, please report with:
- Screenshot of the issue
- Browser console log (F12 → Console → copy all)
- Python console log
- MT5 version and broker name
- Operating system

---

**Ready to test!** Follow this checklist step by step to verify Phase 2 implementation.
