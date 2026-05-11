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

// Concurrency guard for SMC snapshot fetches
let snapshotFetchInProgress = false;
// Independent concurrency guard for H1+M15 PRO
let snapshotH1M15FetchInProgress = false;
// Independent concurrency guard for MICRO IMPULSO
let snapshotMicroImpulsoFetchInProgress = false;

// Timeout for snapshot fetch (15 seconds - enough for 10 symbols + Supabase)
const SNAPSHOT_FETCH_TIMEOUT_MS = 15000;

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
 * Check Python version
 */
function checkPythonVersion(pythonCmd) {
  return new Promise((resolve) => {
    const versionProcess = spawn(pythonCmd, ['--version'], {
      stdio: ['pipe', 'pipe', 'pipe']
    });
    
    let versionOutput = '';
    
    versionProcess.stdout.on('data', (data) => {
      versionOutput += data.toString();
    });
    
    versionProcess.stderr.on('data', (data) => {
      versionOutput += data.toString();
    });
    
    versionProcess.on('close', (code) => {
      if (code === 0 && versionOutput) {
        // Parse version (e.g., "Python 3.11.0" or "Python 3.14.0")
        const match = versionOutput.match(/Python (\d+)\.(\d+)\.(\d+)/);
        if (match) {
          const major = parseInt(match[1]);
          const minor = parseInt(match[2]);
          resolve({ success: true, major, minor, full: versionOutput.trim() });
        } else {
          resolve({ success: false, error: 'Could not parse version' });
        }
      } else {
        resolve({ success: false, error: 'Python not found' });
      }
    });
    
    versionProcess.on('error', () => {
      resolve({ success: false, error: 'Python not found' });
    });
  });
}

/**
 * Select best Python executable
 */
async function selectPythonExecutable() {
  const isWindows = process.platform === 'win32';
  
  // List of Python commands to try, in order of preference
  const pythonCommands = isWindows 
    ? ['py', 'python'] // On Windows, try py launcher first
    : ['python3.11', 'python3', 'python'];
  
  let selectedPython = null;
  let selectedVersion = null;
  
  // Try py -3.11 on Windows
  if (isWindows) {
    console.log('Checking: py -3.11');
    const py311Process = spawn('py', ['-3.11', '--version'], {
      stdio: ['pipe', 'pipe', 'pipe']
    });
    
    const py311Available = await new Promise((resolve) => {
      let versionOutput = '';
      
      py311Process.stdout.on('data', (data) => {
        versionOutput += data.toString();
      });
      
      py311Process.stderr.on('data', (data) => {
        versionOutput += data.toString();
      });
      
      py311Process.on('close', (code) => {
        if (code === 0 && versionOutput.includes('3.11')) {
          const match = versionOutput.match(/Python (\d+)\.(\d+)\.(\d+)/);
          if (match) {
            resolve({
              success: true,
              cmd: 'py',
              args: ['-3.11'],
              major: parseInt(match[1]),
              minor: parseInt(match[2]),
              full: versionOutput.trim()
            });
          } else {
            resolve({ success: false });
          }
        } else {
          resolve({ success: false });
        }
      });
      
      py311Process.on('error', () => {
        resolve({ success: false });
      });
    });
    
    if (py311Available.success) {
      console.log('PYTHON EXEC SELECTED: py -3.11');
      console.log('PYTHON VERSION:', py311Available.full);
      return { cmd: 'py', args: ['-3.11'], version: py311Available };
    }
  }
  
  // Try other Python commands
  for (const cmd of pythonCommands) {
    console.log(`Checking: ${cmd}`);
    const version = await checkPythonVersion(cmd);
    
    if (version.success) {
      console.log(`Found ${cmd}: Python ${version.major}.${version.minor}`);
      
      // Check if Python 3.14
      if (version.major === 3 && version.minor === 14) {
        console.error('❌ Python 3.14 no compatible. Instala Python 3.11.');
        console.error('   Supabase 2.3.0 no funciona con Python 3.14.');
        console.error('   Descarga Python 3.11 desde: https://www.python.org/downloads/');
        throw new Error('Python 3.14 no compatible. Instala Python 3.11.');
      }
      
      // Prefer Python 3.11
      if (version.major === 3 && version.minor === 11) {
        console.log('PYTHON EXEC SELECTED:', cmd);
        console.log('PYTHON VERSION:', version.full);
        return { cmd, args: [], version };
      }
      
      // Store as fallback if no 3.11 found yet
      if (!selectedPython) {
        selectedPython = cmd;
        selectedVersion = version;
      }
    }
  }
  
  // Use fallback if no 3.11 found
  if (selectedPython) {
    console.log('PYTHON EXEC SELECTED:', selectedPython);
    console.log('PYTHON VERSION:', selectedVersion.full);
    console.warn('⚠️ Python 3.11 recomendado. Versión actual puede tener problemas con Supabase.');
    return { cmd: selectedPython, args: [], version: selectedVersion };
  }
  
  // No Python found
  throw new Error('No se encontró Python. Instala Python 3.11.');
}

/**
 * Start Python backend process
 */
async function startPythonBackend() {
  console.log('🐍 Starting Python backend...');
  
  try {
    // Select best Python executable
    const pythonExec = await selectPythonExecutable();
    
    // CRITICAL LOGS: Confirm Python backend path and executable
    console.log('PYTHON BACKEND CWD:', path.dirname(PYTHON_BACKEND.script));
    console.log('PYTHON BACKEND SCRIPT:', PYTHON_BACKEND.script);
    
    // Build command arguments
    const spawnArgs = [...pythonExec.args, PYTHON_BACKEND.script];
    
    return new Promise((resolve, reject) => {
      pythonProcess = spawn(pythonExec.cmd, spawnArgs, {
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
  } catch (error) {
    console.error('❌ Error selecting Python executable:', error.message);
    throw error;
  }
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
  // Prevent concurrent snapshot fetches
  if (snapshotFetchInProgress) {
    console.log('SNAPSHOT FETCH SKIPPED_ALREADY_RUNNING (main process)');
    return { success: false, error: 'SNAPSHOT_ALREADY_RUNNING' };
  }

  snapshotFetchInProgress = true;
  console.log('SNAPSHOT FETCH START (main process)');

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), SNAPSHOT_FETCH_TIMEOUT_MS);

  try {
    const url = `http://${PYTHON_BACKEND.host}:${PYTHON_BACKEND.port}/api/smc/m15-pro/snapshot`;
    
    const response = await fetch(url, { signal: controller.signal });
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    const data = await response.json();
    clearTimeout(timeoutId);
    console.log(`SNAPSHOT FETCH OK (main process) - ${Array.isArray(data) ? data.length : '?'} rows`);
    return { success: true, data };
  } catch (error) {
    const reason = error.name === 'AbortError' ? 'TIMEOUT' : error.message;
    console.error(`SNAPSHOT FETCH ERROR (main process): ${reason}`);
    return { success: false, error: reason };
  } finally {
    clearTimeout(timeoutId);
    snapshotFetchInProgress = false;
  }
});

/**
 * IPC Handler: Get SMC H1+M15 PRO snapshot (FASE 3B)
 */
ipcMain.handle('get-smc-h1m15-pro-snapshot', async () => {
  if (snapshotH1M15FetchInProgress) {
    console.log('H1M15 SNAPSHOT FETCH SKIPPED_ALREADY_RUNNING (main process)');
    return { success: false, error: 'SNAPSHOT_ALREADY_RUNNING' };
  }

  snapshotH1M15FetchInProgress = true;
  console.log('H1M15 SNAPSHOT FETCH START (main process)');

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), SNAPSHOT_FETCH_TIMEOUT_MS);

  try {
    const url = `http://${PYTHON_BACKEND.host}:${PYTHON_BACKEND.port}/api/smc/h1-m15-pro/snapshot`;

    const response = await fetch(url, { signal: controller.signal });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();
    clearTimeout(timeoutId);
    console.log(`H1M15 SNAPSHOT FETCH OK (main process) - ${Array.isArray(data) ? data.length : '?'} rows`);
    return { success: true, data };
  } catch (error) {
    const reason = error.name === 'AbortError' ? 'TIMEOUT' : error.message;
    console.error(`H1M15 SNAPSHOT FETCH ERROR (main process): ${reason}`);
    return { success: false, error: reason };
  } finally {
    clearTimeout(timeoutId);
    snapshotH1M15FetchInProgress = false;
  }
});

/**
 * IPC Handler: Get SMC MICRO IMPULSO snapshot (FASE 4)
 */
ipcMain.handle('get-smc-micro-impulso-snapshot', async () => {
  if (snapshotMicroImpulsoFetchInProgress) {
    console.log('MICRO_IMPULSO SNAPSHOT FETCH SKIPPED_ALREADY_RUNNING (main process)');
    return { success: false, error: 'SNAPSHOT_ALREADY_RUNNING' };
  }

  snapshotMicroImpulsoFetchInProgress = true;
  console.log('MICRO_IMPULSO SNAPSHOT FETCH START (main process)');

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), SNAPSHOT_FETCH_TIMEOUT_MS);

  try {
    const url = `http://${PYTHON_BACKEND.host}:${PYTHON_BACKEND.port}/api/smc/micro-impulso/snapshot`;

    const response = await fetch(url, { signal: controller.signal });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();
    clearTimeout(timeoutId);
    console.log(`MICRO_IMPULSO SNAPSHOT FETCH OK (main process) - ${Array.isArray(data) ? data.length : '?'} rows`);
    return { success: true, data };
  } catch (error) {
    const reason = error.name === 'AbortError' ? 'TIMEOUT' : error.message;
    console.error(`MICRO_IMPULSO SNAPSHOT FETCH ERROR (main process): ${reason}`);
    return { success: false, error: reason };
  } finally {
    clearTimeout(timeoutId);
    snapshotMicroImpulsoFetchInProgress = false;
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
