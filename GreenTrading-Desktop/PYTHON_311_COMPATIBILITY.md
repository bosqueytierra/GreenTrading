# Python 3.11 Compatibility Fix

## Problem

GreenTrading Desktop backend was failing on systems with Python 3.14 due to incompatibility with Supabase 2.3.0:

```
AttributeError: 'typing.Union' object has no attribute '__module__'
```

This error occurs in the dependency chain: `supabase → postgrest → httpx → httpcore`

## Solution

The application now automatically detects and selects the appropriate Python version, with preference for Python 3.11.

### Changes Made

#### 1. **main.js - Python Version Detection**

Added two new functions:

- `checkPythonVersion(pythonCmd)`: Checks the version of a Python executable
- `selectPythonExecutable()`: Selects the best available Python executable

**Priority order on Windows:**
1. `py -3.11` (Python 3.11 via Windows py launcher)
2. `py` (default Python via launcher)
3. `python` (fallback)

**Priority order on Linux/Mac:**
1. `python3.11`
2. `python3`
3. `python`

**Python 3.14 Detection:**
- If Python 3.14 is detected, the application will **fail with a clear error message**:
  ```
  ❌ Python 3.14 no compatible. Instala Python 3.11.
     Supabase 2.3.0 no funciona con Python 3.14.
     Descarga Python 3.11 desde: https://www.python.org/downloads/
  ```

**Logging:**
The application now logs:
```
PYTHON EXEC SELECTED: py -3.11
PYTHON VERSION: Python 3.11.0
```

#### 2. **README.md - Documentation Updates**

**Prerequisites section:**
- Changed from "Python (3.8 or higher)" to **"Python 3.11 (REQUIRED)"**
- Added warning: "⚠️ DO NOT USE Python 3.14"
- Added link to download Python 3.11

**Installation instructions:**
- Updated pip install command to use `py -3.11 -m pip install`
- Added verification step: `py -3.11 --version`

**Troubleshooting section:**
- Added dedicated section for Python 3.14 compatibility error
- Explained why Python 3.14 doesn't work
- Provided step-by-step solution

#### 3. **requirements.txt - Version Documentation**

Added comments at the top:
```
# IMPORTANT: Requires Python 3.11 (NOT Python 3.14)
# Python 3.14 has compatibility issues with Supabase 2.3.0
```

Added note on Supabase dependency:
```
# Supabase integration (requires Python 3.11, NOT compatible with Python 3.14)
supabase==2.3.0
```

## Testing

### Expected Behavior

**Scenario 1: Python 3.11 is installed**
```
Checking: py -3.11
PYTHON EXEC SELECTED: py -3.11
PYTHON VERSION: Python 3.11.0
🐍 Starting Python backend...
✅ Python backend ready
```

**Scenario 2: Only Python 3.14 is installed**
```
Checking: py -3.11
Checking: py
Found py: Python 3.14
❌ Python 3.14 no compatible. Instala Python 3.11.
   Supabase 2.3.0 no funciona con Python 3.14.
   Descarga Python 3.11 desde: https://www.python.org/downloads/
❌ Error selecting Python executable: Python 3.14 no compatible. Instala Python 3.11.
```

**Scenario 3: Python 3.10 is installed (fallback)**
```
Checking: py -3.11
Checking: py
Found py: Python 3.10
PYTHON EXEC SELECTED: py
PYTHON VERSION: Python 3.10.0
⚠️ Python 3.11 recomendado. Versión actual puede tener problemas con Supabase.
🐍 Starting Python backend...
```

## User Impact

- **Windows users** with Python 3.14 will see a clear error message and installation instructions
- **Windows users** with Python 3.11 installed will automatically use it via `py -3.11`
- **All users** will see which Python executable and version is being used
- **Documentation** clearly states Python 3.11 requirement

## Technical Details

### Why Python 3.11?

- **Supabase 2.3.0** was tested and works with Python 3.11
- **Python 3.14** introduced changes to the `typing` module that break `httpcore`
- The specific error is in type introspection used by httpcore's type checking

### Why not upgrade Supabase?

- Supabase 2.3.0 is the current stable version used in the project
- Upgrading dependencies could introduce breaking changes
- Python 3.11 is a mature, stable version suitable for production use

### Windows py launcher

The Windows `py` launcher allows multiple Python versions to coexist:
- `py -3.11` explicitly selects Python 3.11
- `py` uses the default Python version
- This is the recommended way to manage Python versions on Windows

## No Impact Areas (As Required)

✅ **SMC logic** - Not modified
✅ **Frontend** - Not modified  
✅ **Supabase SQL** - Not modified
✅ **Only runtime Python compatibility** - Correct

## Files Modified

1. `GreenTrading-Desktop/main.js` - Added Python version detection
2. `GreenTrading-Desktop/README.md` - Updated documentation
3. `GreenTrading-Desktop/requirements.txt` - Added version notes

## Verification Checklist

- [x] Python version detection implemented
- [x] Python 3.14 is blocked with clear error message
- [x] Python 3.11 is preferred via `py -3.11`
- [x] Logs show `PYTHON EXEC SELECTED` and `PYTHON VERSION`
- [x] README.md documents Python 3.11 requirement
- [x] requirements.txt documents Python 3.11 requirement
- [x] Troubleshooting guide added for Python 3.14 error
- [x] main.js syntax validated
- [x] No changes to SMC logic
- [x] No changes to frontend
- [x] No changes to Supabase SQL

## Future Considerations

If Python 3.14 compatibility is needed in the future:
1. Upgrade Supabase client library to a version that supports Python 3.14
2. Test thoroughly with all dependencies
3. Update version detection to allow Python 3.14
