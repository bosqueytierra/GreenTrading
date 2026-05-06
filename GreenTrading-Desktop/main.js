/**
 * GreenTrading Desktop - Main Process
 * 
 * Phase 1: Minimal proof of concept
 * - Launch Electron window
 * - Spawn Python backend
 * - Handle IPC communication
 */

const { app, BrowserWindow, ipcMain } = require('electron');
const { spawn } = require('child_process');
const path = require('path');

let mainWindow = null;
let pythonProcess = null;

// Python backend configuration
const PYTHON_BACKEND = {
  port: 8765,
  host: 'localhost',
  script: path.join(__dirname, 'backend', 'api_server.py')
};

/**
 * Create the main application window
 */
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    },
    icon: path.join(__dirname, 'frontend', 'assets', 'images', 'Green.png')
  });

  // Phase 2: Load dashboard instead of test page
  mainWindow.loadFile(path.join(__dirname, 'frontend', 'pages', 'dashboard.html'));
  
  // Open DevTools in development
  if (process.env.NODE_ENV === 'development') {
    mainWindow.webContents.openDevTools();
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  console.log('✅ Electron window created');
}

/**
 * Start Python backend process
 */
function startPythonBackend() {
  return new Promise((resolve, reject) => {
    console.log('🐍 Starting Python backend...');
    
    // Determine Python command (python or python3)
    const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
    
    // CRITICAL LOGS: Confirm Python backend path and executable
    console.log('PYTHON BACKEND CWD:', path.dirname(PYTHON_BACKEND.script));
    console.log('PYTHON BACKEND SCRIPT:', PYTHON_BACKEND.script);
    console.log('PYTHON EXEC:', pythonCmd);
    
    pythonProcess = spawn(pythonCmd, [PYTHON_BACKEND.script], {
      stdio: ['pipe', 'pipe', 'pipe']
    });

    pythonProcess.stdout.on('data', (data) => {
      const message = data.toString();
      console.log(`[Python] ${message}`);
      
      // Check if backend is ready
      if (message.includes('Uvicorn running on')) {
        console.log('✅ Python backend ready');
        resolve();
      }
    });

    pythonProcess.stderr.on('data', (data) => {
      console.error(`[Python Error] ${data.toString()}`);
    });

    pythonProcess.on('error', (error) => {
      console.error('❌ Failed to start Python backend:', error);
      reject(error);
    });

    pythonProcess.on('close', (code) => {
      console.log(`Python backend exited with code ${code}`);
      pythonProcess = null;
    });

    // Timeout if backend doesn't start in 10 seconds
    setTimeout(() => {
      if (pythonProcess && !pythonProcess.killed) {
        resolve(); // Continue anyway
      }
    }, 10000);
  });
}

/**
 * Stop Python backend process
 */
function stopPythonBackend() {
  if (pythonProcess) {
    console.log('🛑 Stopping Python backend...');
    pythonProcess.kill();
    pythonProcess = null;
  }
}

/**
 * IPC Handler: Get one candle from MT5
 */
ipcMain.handle('get-candle', async (event, symbol, timeframe) => {
  try {
    const url = `http://${PYTHON_BACKEND.host}:${PYTHON_BACKEND.port}/api/candle/${symbol}/${timeframe}`;
    console.log(`Fetching candle from: ${url}`);
    
    const response = await fetch(url);
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    const data = await response.json();
    return { success: true, data };
  } catch (error) {
    console.error('Error fetching candle:', error);
    return { success: false, error: error.message };
  }
});

/**
 * IPC Handler: Check backend status
 */
ipcMain.handle('check-status', async () => {
  try {
    const url = `http://${PYTHON_BACKEND.host}:${PYTHON_BACKEND.port}/api/status`;
    const response = await fetch(url);
    
    if (!response.ok) {
      throw new Error('Backend not responding');
    }
    
    const data = await response.json();
    return { success: true, data };
  } catch (error) {
    return { success: false, error: error.message };
  }
});

/**
 * IPC Handler: Get symbols snapshot (Phase 2)
 */
ipcMain.handle('get-symbols-snapshot', async () => {
  try {
    const url = `http://${PYTHON_BACKEND.host}:${PYTHON_BACKEND.port}/api/symbols/snapshot`;
    console.log(`Fetching symbols snapshot from: ${url}`);
    
    const response = await fetch(url);
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    const data = await response.json();
    return { success: true, data };
  } catch (error) {
    console.error('Error fetching symbols snapshot:', error);
    return { success: false, error: error.message };
  }
});

/**
 * IPC Handler: Get SMC M15 PRO snapshot (Phase 3)
 */
ipcMain.handle('get-smc-m15-pro-snapshot', async () => {
  try {
    const url = `http://${PYTHON_BACKEND.host}:${PYTHON_BACKEND.port}/api/smc/m15-pro/snapshot`;
    console.log(`Fetching SMC M15 PRO snapshot from: ${url}`);
    
    const response = await fetch(url);
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    const data = await response.json();
    return { success: true, data };
  } catch (error) {
    console.error('Error fetching SMC snapshot:', error);
    return { success: false, error: error.message };
  }
});

/**
 * App lifecycle: Ready
 */
app.whenReady().then(async () => {
  try {
    // Start Python backend first
    await startPythonBackend();
    
    // Then create window
    createWindow();
    
    console.log('✅ Application ready');
  } catch (error) {
    console.error('❌ Failed to start application:', error);
    app.quit();
  }
});

/**
 * App lifecycle: All windows closed
 */
app.on('window-all-closed', () => {
  stopPythonBackend();
  
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

/**
 * App lifecycle: Activate (macOS)
 */
app.on('activate', () => {
  if (mainWindow === null) {
    createWindow();
  }
});

/**
 * App lifecycle: Before quit
 */
app.on('before-quit', () => {
  stopPythonBackend();
});

console.log('🚀 GreenTrading Desktop starting...');
