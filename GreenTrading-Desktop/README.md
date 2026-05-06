# GreenTrading Desktop

**Phase 1: Minimal Stack Validation - Proof of Concept**

Desktop application for trading analysis using MetaTrader 5, built with Electron + Python.

---

## 🎯 Phase 1 Objectives

✅ **ONLY Phase 1 implementation - Stack validation:**

1. Electron opens a window
2. Python backend starts correctly
3. MT5 connects correctly
4. Read ONE real candle from MT5
5. Display it on screen

**NOT included in Phase 1:**
- ❌ No full dashboard
- ❌ No historical data
- ❌ No strategies (SMC)
- ❌ No complex SQLite
- ❌ No large migrations

---

## 🏗️ Architecture

> **📖 IMPORTANT**: Read [ARCHITECTURE_CLARIFICATION.md](./ARCHITECTURE_CLARIFICATION.md) for detailed explanation of data flow and storage strategy.

### Corrected Architecture (based on feedback):

1. **NO almacenar todas las velas en SQLite**
   - Las velas se leen desde MT5 **directamente por el engine**
   - Engine puede leer las velas que necesite (ej: 500-1000+)
   - Se procesan en memoria
   - Se descartan después del procesamiento
   - SQLite guarda: setups con contexto pre-calculado, historial, estados, TP/SL, métricas
   - OPCIONAL: Buffer limitado de 300-500 velas recientes para optimización

2. **Engine NO depende de SQLite**
   - Flujo correcto: `MT5 → engine (lee desde MT5) → resultado → SQLite`
   - Engine lee directamente de MT5 las velas que necesita
   - SQLite solo recibe resultados procesados (setups, estados)
   - Historial NO requiere recalcular velas antiguas (se guarda pre-calculado)

3. **Arquitectura event-driven** (no polling)
   - Python detecta cambios
   - Electron recibe evento
   - UI actualiza
   - Sin `setInterval(fetch...)`

### Data Flow

```
┌─────────────┐
│   Electron  │  (Frontend - UI)
│   Window    │
└──────┬──────┘
       │ IPC (contextBridge)
       │
┌──────▼──────┐
│   main.js   │  (Main Process)
└──────┬──────┘
       │ HTTP REST
       │ localhost:8765
┌──────▼──────┐
│   FastAPI   │  (Python Backend)
│  api_server │
└──────┬──────┘
       │ MetaTrader5 API
       │ (In-memory only)
┌──────▼──────┐
│     MT5     │  (Data Source)
│  Installed  │
└─────────────┘
```

---

## 📁 Project Structure

```
GreenTrading-Desktop/
├── frontend/                    # Electron frontend
│   ├── assets/
│   │   ├── css/
│   │   │   └── style.css       # Minimal styling
│   │   ├── js/
│   │   │   └── app.js          # Frontend logic
│   │   └── images/
│   │       └── Green.png       # Logo (copy from main repo)
│   └── pages/
│       └── index.html          # Main page
│
├── backend/                     # Python backend
│   └── api_server.py           # FastAPI server with MT5
│
├── engines/                     # SMC engines (future phases)
│   └── (empty for Phase 1)
│
├── main.js                      # Electron main process
├── preload.js                   # IPC bridge
├── package.json                 # Node dependencies
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

---

## 🚀 Installation & Setup

### Prerequisites

1. **Node.js** (v18 or higher)
2. **Python** (3.8 or higher)
3. **MetaTrader 5** installed and running on Windows

### Step 1: Install Node.js dependencies

```bash
cd GreenTrading-Desktop
npm install
```

### Step 2: Install Python dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Copy logo (optional)

```bash
# Copy logo from main repository
cp ../graficos/Green.png frontend/assets/images/
```

### Step 4: Ensure MT5 is running

- Open MetaTrader 5
- Login to your account
- Leave it running

---

## ▶️ Running the Application

### Development Mode

```bash
npm start
```

This will:
1. Start the Python backend (port 8765)
2. Launch Electron window
3. Connect to MT5
4. Display the Phase 1 test interface

### What to expect:

1. **Electron window opens** with a clean interface
2. **Status section** shows:
   - ✅ Electron: Running
   - ✅ Python Backend: Connected
   - ✅ MT5 Connection: Connected - [MT5 Terminal Name]
3. **Candle test section** allows you to:
   - Select a symbol (Boom/Crash)
   - Select a timeframe (M1/M15/H1)
   - Click "Get Candle from MT5"
4. **Result displays** the latest candle data:
   - Time, Open, High, Low, Close, Volume

---

## 🧪 Testing Phase 1

### Manual Test Checklist:

- [ ] Electron window opens successfully
- [ ] Python backend starts (check console)
- [ ] MT5 status shows "Connected"
- [ ] Click "Get Candle from MT5" button
- [ ] Candle data displays correctly
- [ ] Try different symbols (Boom/Crash)
- [ ] Try different timeframes (M1/M15/H1)
- [ ] Check for errors in console

### Expected Results:

✅ **Success**: You should see real candle data from MT5 displayed in the window

❌ **Failure scenarios**:
- MT5 not running → "MT5 Disconnected" status
- Symbol not available → Error message
- Backend not responding → Connection error

---

## 🔧 Troubleshooting

### Python backend not starting

```bash
# Run backend manually to see errors
python backend/api_server.py
```

### MT5 not connecting

1. Ensure MT5 is running
2. Ensure you're logged into an account
3. Check MT5 terminal settings (Tools → Options → Expert Advisors → "Allow automated trading")

### Electron not starting

```bash
# Check Node.js version
node --version  # Should be v18+

# Reinstall dependencies
rm -rf node_modules
npm install
```

---

## 📝 Phase 1 Complete - Next Steps

Once Phase 1 is working:

1. ✅ **Validate stack**: Electron ↔ Python ↔ MT5 communication works
2. ✅ **Confirm architecture**: Event-driven, in-memory processing
3. ✅ **Verify MT5 integration**: Real candle data can be read

**Then move to Phase 2:**
- Implement event-driven architecture (WebSockets)
- Add limited candle buffer (300-500 candles)
- Integrate SMC engines
- Add minimal SQLite for setups only

---

## 🎓 Key Concepts

### Why NO full SQLite for candles?

- **Memory efficiency**: Don't replicate Supabase's massive storage
- **Performance**: Process in-memory, discard after analysis
- **Simplicity**: SQLite only for results (setups, history, metrics)

### Why event-driven instead of polling?

- **Efficiency**: No wasteful `setInterval` requests
- **Real-time**: Instant updates when data changes
- **Scalability**: Better for future features

### Why engines don't depend on SQLite?

- **Separation**: MT5 → engine (pure calculation) → SQLite (persistence)
- **Testability**: Engines can be tested without database
- **Flexibility**: Easy to swap storage backend

---

## 📄 License

MIT License - GreenTrading Team

---

## 🤝 Contributing

Phase 1 is a minimal proof of concept. 

**Do NOT add features yet!**

Wait for Phase 1 validation before proceeding to Phase 2.

---

**Phase 1 Status**: ✅ Implementation Complete - Ready for Testing
