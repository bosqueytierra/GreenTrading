# Testing Guide - Python 3.11 Compatibility

## Overview

This guide provides step-by-step instructions to test the Python 3.11 compatibility fix for GreenTrading Desktop.

## Test Prerequisites

- Windows PC (primary target platform)
- Access to install Python versions
- MetaTrader 5 installed and running

## Test Scenarios

### Scenario 1: Python 3.11 Available ✅

**Setup:**
1. Install Python 3.11 from https://www.python.org/downloads/
2. Verify: `py -3.11 --version` shows Python 3.11.x

**Test:**
```bash
cd GreenTrading-Desktop
npm start
```

**Expected Console Output:**
```
Checking: py -3.11
PYTHON EXEC SELECTED: py -3.11
PYTHON VERSION: Python 3.11.x
PYTHON BACKEND CWD: <path>/backend
PYTHON BACKEND SCRIPT: <path>/backend/api_server.py
🐍 Starting Python backend...
[Python] INFO:     Started server process...
[Python] INFO:     Uvicorn running on http://127.0.0.1:8765
✅ Python backend ready
✅ Electron window created
✅ Application ready
```

**Expected Behavior:**
- Application starts successfully
- Backend connects to MT5
- Dashboard displays data
- No errors in console

---

### Scenario 2: Python 3.14 Detected ❌

**Setup:**
1. Install Python 3.14 (if available)
2. Ensure Python 3.11 is NOT installed
3. Verify: `py --version` shows Python 3.14.x

**Test:**
```bash
cd GreenTrading-Desktop
npm start
```

**Expected Console Output:**
```
Checking: py -3.11
Checking: py
Found py: Python 3.14
❌ Python 3.14 no compatible. Instala Python 3.11.
   Supabase 2.3.0 no funciona con Python 3.14.
   Descarga Python 3.11 desde: https://www.python.org/downloads/
❌ Error selecting Python executable: Python 3.14 no compatible. Instala Python 3.11.
❌ Failed to start application: Python 3.14 no compatible. Instala Python 3.11.
```

**Expected Behavior:**
- Application fails to start
- Clear error message shown
- Instructions provided
- User knows exactly what to do

---

### Scenario 3: Python 3.10/3.12 (Fallback) ⚠️

**Setup:**
1. Install Python 3.10 or 3.12
2. Ensure Python 3.11 is NOT installed
3. Verify: `py --version` shows Python 3.10.x or 3.12.x

**Test:**
```bash
cd GreenTrading-Desktop
npm start
```

**Expected Console Output:**
```
Checking: py -3.11
Checking: py
Found py: Python 3.10 (or 3.12)
PYTHON EXEC SELECTED: py
PYTHON VERSION: Python 3.10.x (or 3.12.x)
⚠️ Python 3.11 recomendado. Versión actual puede tener problemas con Supabase.
PYTHON BACKEND CWD: <path>/backend
PYTHON BACKEND SCRIPT: <path>/backend/api_server.py
🐍 Starting Python backend...
[Python] INFO:     Started server process...
[Python] INFO:     Uvicorn running on http://127.0.0.1:8765
✅ Python backend ready
```

**Expected Behavior:**
- Application starts with warning
- Backend may or may not work (depends on Supabase compatibility)
- User is warned to use Python 3.11

---

### Scenario 4: Multiple Python Versions ✅

**Setup:**
1. Install both Python 3.11 and Python 3.14
2. Verify both are available:
   - `py -3.11 --version` → Python 3.11.x
   - `py -3.14 --version` → Python 3.14.x
   - `py --version` → Python 3.14.x (default)

**Test:**
```bash
cd GreenTrading-Desktop
npm start
```

**Expected Console Output:**
```
Checking: py -3.11
PYTHON EXEC SELECTED: py -3.11
PYTHON VERSION: Python 3.11.x
🐍 Starting Python backend...
✅ Python backend ready
```

**Expected Behavior:**
- Application automatically selects Python 3.11
- Python 3.14 is NOT used (even though it's the default)
- Application works correctly

---

### Scenario 5: No Python Installed ❌

**Setup:**
1. Ensure Python is not installed
2. Verify: `py --version` and `python --version` fail

**Test:**
```bash
cd GreenTrading-Desktop
npm start
```

**Expected Console Output:**
```
Checking: py -3.11
Checking: py
Checking: python
❌ Error selecting Python executable: No se encontró Python. Instala Python 3.11.
❌ Failed to start application: No se encontró Python. Instala Python 3.11.
```

**Expected Behavior:**
- Application fails to start
- Clear error message
- Instructions to install Python 3.11

---

## Installation Testing

### Test Python 3.11 Installation Instructions

**Verify README.md instructions work:**

1. Follow the README.md installation steps:
   ```bash
   # On Windows
   py -3.11 -m pip install -r requirements.txt
   ```

2. Verify installation:
   ```bash
   py -3.11 -m pip list
   ```

3. Check for key packages:
   - fastapi==0.109.1
   - uvicorn==0.27.0
   - MetaTrader5==5.0.5735
   - supabase==2.3.0

**Expected:**
- All dependencies install without errors
- No compatibility warnings

---

## Backend Testing

### Test Backend with Python 3.11

**Manual backend start:**
```bash
cd GreenTrading-Desktop/backend
py -3.11 api_server.py
```

**Expected Output:**
```
INFO:     Started server process [PID]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8765 (Press CTRL+C to quit)
```

**API Testing:**
```bash
# In another terminal
curl http://localhost:8765/api/status
```

**Expected Response:**
```json
{
  "status": "online",
  "mt5_connected": true,
  "terminal": "MetaTrader 5"
}
```

---

## Edge Cases

### Edge Case 1: Python 3.14 with py -3.11 flag

**Setup:**
- Only Python 3.14 installed
- User tries: `py -3.11`

**Expected:**
- Command fails (Python 3.11 not installed)
- Application detects this and shows error

### Edge Case 2: Corrupted Python Installation

**Setup:**
- Python installed but broken
- `python --version` fails or hangs

**Expected:**
- Application times out or shows error
- Clear message about Python not working

### Edge Case 3: Python in PATH but not py launcher

**Setup:**
- Python installed without py launcher
- Only `python` command works

**Expected:**
- Application falls back to `python` command
- Detects version correctly
- Works or fails based on version

---

## Verification Checklist

After all tests, verify:

- [ ] Python 3.11 is automatically selected when available
- [ ] Python 3.14 is blocked with clear error
- [ ] Logs show PYTHON EXEC SELECTED
- [ ] Logs show PYTHON VERSION
- [ ] README.md instructions are accurate
- [ ] Error messages are helpful
- [ ] Application works with Python 3.11
- [ ] Application fails gracefully with Python 3.14
- [ ] No changes to SMC logic
- [ ] No changes to frontend
- [ ] No changes to Supabase SQL

---

## Troubleshooting Test Issues

### Issue: "py command not found"

**On Windows:**
- Reinstall Python with "Add Python to PATH" option
- Ensure "py launcher" is installed
- Restart terminal

### Issue: "Module not found" errors

**Solution:**
```bash
py -3.11 -m pip install --upgrade pip
py -3.11 -m pip install -r requirements.txt
```

### Issue: MT5 not connecting

**Solution:**
1. Ensure MT5 is running
2. Login to MT5 account
3. Enable Expert Advisors (Tools → Options → Expert Advisors)
4. Restart application

---

## Performance Testing

### Startup Time
- Measure time from `npm start` to "Application ready"
- Expected: < 15 seconds
- Python detection should add < 2 seconds

### Backend Response Time
- Test `/api/status` endpoint
- Expected: < 100ms

### Version Detection Overhead
- Time from start to "PYTHON EXEC SELECTED"
- Expected: < 2 seconds

---

## Security Considerations

### Tested:
- ✅ CodeQL security scan passed
- ✅ No command injection vulnerabilities
- ✅ Python executable path validated
- ✅ No arbitrary code execution

### Not spawning:
- ❌ User-provided Python paths (only standard commands)
- ❌ Concatenated commands
- ❌ Shell execution with shell: true

---

## Documentation Accuracy

Verify these documents match implementation:
- [ ] README.md prerequisites section
- [ ] README.md installation steps
- [ ] README.md troubleshooting section
- [ ] requirements.txt comments
- [ ] PYTHON_311_COMPATIBILITY.md
- [ ] This testing guide

---

## Success Criteria

The fix is successful if:

1. ✅ Users with Python 3.11 can run the application
2. ✅ Users with Python 3.14 see a clear error message
3. ✅ Users can follow documentation to install Python 3.11
4. ✅ Application automatically selects Python 3.11 when available
5. ✅ Console logs clearly show Python selection
6. ✅ No changes to SMC logic, frontend, or Supabase SQL
7. ✅ All validation tests pass

---

## Rollback Plan

If issues are found:

1. Revert to previous commit
2. Use simple Python detection: `python` or `python3`
3. Document Python 3.11 requirement only in README
4. No automatic version detection

---

## Next Steps After Testing

If all tests pass:
1. Merge PR to main branch
2. Update release notes
3. Notify users about Python 3.11 requirement
4. Monitor for Python-related issues

If tests fail:
1. Document failure scenarios
2. Fix issues
3. Re-run validation
4. Repeat until all scenarios pass
