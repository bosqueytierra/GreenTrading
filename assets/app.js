// Configuración de Supabase
const SUPABASE_URL = 'https://rqjmndaqxxgljpubnfkg.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJxam1uZGFxeHhnbGpwdWJuZmtnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc3NDYzOTMsImV4cCI6MjA5MzMyMjM5M30.6WCZP39R9nMoDPgasGxPt6qbR8rvVcB3kX1gJvnKuv0';

// Usuarios válidos
const VALID_USERS = {
    'LCarvajal': 'MarioTonga',
    'SMorales': 'MarioTonga'
};

// Variables globales
let autoRefreshInterval = null;
const AUTO_REFRESH_SECONDS = 30;
let currentUser = null;
// Estrategia seleccionada en dashboard (SMC_M15_PRO o SMC_H1_M15_PRO)
let currentStrategy = 'SMC_M15_PRO';
// Estrategia seleccionada en historial (SMC_M15_PRO o SMC_H1_M15_PRO)
let currentHistoryStrategy = 'SMC_M15_PRO';

// Configuración de estrategias - MAPEO DE TABLAS
// Cada estrategia usa su propia tabla independiente (aislamiento real)
const STRATEGIES = {
    SMC_M15_PRO: {
        name: 'SMC M15 PRO',
        table: 'smc_m15_setups',
        displayName: 'SMC M15 PRO'
    },
    SMC_H1_M15_PRO: {
        name: 'SMC PRO TENDENCIA H1 + CHOCH/BOS (M15)',
        table: 'smc_h1_m15_setups',
        displayName: 'SMC PRO TENDENCIA H1 + CHOCH/BOS (M15)'
    }
};

// Lista de todos los índices
const ALL_INDICES = {
    boom: [
        'Boom 1000 Index',
        'Boom 900 Index',
        'Boom 600 Index',
        'Boom 500 Index',
        'Boom 300 Index'
    ],
    crash: [
        'Crash 1000 Index',
        'Crash 900 Index',
        'Crash 600 Index',
        'Crash 500 Index',
        'Crash 300 Index'
    ]
};

// Configuración SMC
const SWING_LOOKBACK = 3;
const CLOSE_BREAK = true;
const M1_VELAS_ZONA = 15;
const ORDER_BLOCK_LOOKBACK = 20;
const BARRIDA_LOOKBACK = 40;
const MIN_SEGMENT_LENGTH = 10;
const BARRIDA_INITIAL_OFFSET = 5;

// Estados de setup activos (pueden ser actualizados por precio)
const ACTIVE_SETUP_STATES = ['ACTIVA', 'EN_ZONA', 'PROFIT', 'PAUSADA', 'TP'];

// ========================================
// LOGIN LOGIC
// ========================================

document.addEventListener('DOMContentLoaded', () => {
    checkSession();
    setupLoginForm();
});

function checkSession() {
    const savedUser = localStorage.getItem('greenTradingUser');
    if (savedUser) {
        currentUser = savedUser;
        showDashboard();
    } else {
        showLogin();
    }
}

function setupLoginForm() {
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }
    
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', handleLogout);
    }
}

function handleLogin(e) {
    e.preventDefault();
    
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    const errorDiv = document.getElementById('loginError');
    
    if (VALID_USERS[username] && VALID_USERS[username] === password) {
        // Login successful
        currentUser = username;
        localStorage.setItem('greenTradingUser', username);
        errorDiv.textContent = '';
        showDashboard();
    } else {
        // Login failed
        errorDiv.textContent = 'Usuario o contraseña incorrectos';
    }
}

function handleLogout() {
    currentUser = null;
    localStorage.removeItem('greenTradingUser');
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
    }
    showLogin();
}

function showLogin() {
    document.getElementById('loginScreen').style.display = 'flex';
    document.getElementById('dashboardScreen').style.display = 'none';
}

function showDashboard() {
    document.getElementById('loginScreen').style.display = 'none';
    document.getElementById('dashboardScreen').style.display = 'flex';
    document.getElementById('userInfo').textContent = currentUser;
    
    initializeDashboard();
}

// ========================================
// NAVIGATION LOGIC
// ========================================

function initNavigation() {
    // Sidebar toggle
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('sidebar');
    
    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', () => {
            sidebar.classList.toggle('collapsed');
        });
    }
    
    // Navigation links
    const navLinks = document.querySelectorAll('.sidebar-link');
    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const view = link.getAttribute('data-view');
            switchView(view);
        });
    });
    
    // Refresh history button
    const refreshHistoryBtn = document.getElementById('refreshHistoryBtn');
    if (refreshHistoryBtn) {
        refreshHistoryBtn.addEventListener('click', () => {
            updateHistoryTable();
        });
    }
}

function switchView(viewName) {
    // Update active link
    document.querySelectorAll('.sidebar-link').forEach(link => {
        link.classList.remove('active');
        if (link.getAttribute('data-view') === viewName) {
            link.classList.add('active');
        }
    });
    
    // Hide all views
    document.querySelectorAll('.view-content').forEach(view => {
        view.classList.remove('active');
    });
    
    // Show selected view
    const views = {
        'dashboard': 'dashboardView',
        'history': 'historyView',
        'stats': 'statsView',
        'settings': 'settingsView'
    };
    
    const viewId = views[viewName];
    if (viewId) {
        const viewElement = document.getElementById(viewId);
        if (viewElement) {
            viewElement.classList.add('active');
        }
    }
    
    // Update page title
    const titles = {
        'dashboard': 'Dashboard en vivo',
        'history': 'Historial SMC M15 PRO',
        'stats': 'Estadísticas',
        'settings': 'Configuración'
    };
    
    const pageTitle = document.getElementById('pageTitle');
    if (pageTitle) {
        pageTitle.textContent = titles[viewName] || 'GreenTrading';
    }
    
    // Load data if needed
    if (viewName === 'history') {
        updateHistoryTable();
    }
}

// ========================================
// DASHBOARD LOGIC
// ========================================

function initializeDashboard() {
    // Verificar configuración
    if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
        console.error('Configuración de Supabase no disponible');
        return;
    }
    
    // Initialize navigation
    initNavigation();
    
    // Initialize strategy tabs
    initStrategyTabs();
    
    // Event listeners
    const refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', fetchAllIndices);
    }
    
    // Cargar datos iniciales
    fetchAllIndices();
    
    // Iniciar auto-refresh
    startAutoRefresh();
}

// ========================================
// STRATEGY TABS LOGIC
// ========================================

function initStrategyTabs() {
    // Dashboard tabs
    const dashboardTabs = document.querySelectorAll('#dashboardView .strategy-tab');
    dashboardTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const strategy = tab.getAttribute('data-strategy');
            switchDashboardStrategy(strategy);
        });
    });
    
    // History tabs
    const historyTabs = document.querySelectorAll('#historyView .strategy-tab');
    historyTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const strategy = tab.getAttribute('data-strategy');
            switchHistoryStrategy(strategy);
        });
    });
}

function switchDashboardStrategy(strategy) {
    currentStrategy = strategy;
    
    // Update active tab
    const dashboardTabs = document.querySelectorAll('#dashboardView .strategy-tab');
    dashboardTabs.forEach(tab => {
        if (tab.getAttribute('data-strategy') === strategy) {
            tab.classList.add('active');
        } else {
            tab.classList.remove('active');
        }
    });
    
    // Cada estrategia lee/escribe de su propia tabla independiente
    // SMC M15 PRO → smc_m15_setups
    // SMC H1+M15 PRO → smc_h1_m15_setups
    // Reload dashboard with new strategy
    fetchAllIndices();
}

function switchHistoryStrategy(strategy) {
    currentHistoryStrategy = strategy;
    
    // Update active tab
    const historyTabs = document.querySelectorAll('#historyView .strategy-tab');
    historyTabs.forEach(tab => {
        if (tab.getAttribute('data-strategy') === strategy) {
            tab.classList.add('active');
        } else {
            tab.classList.remove('active');
        }
    });
    
    // Update history title
    const historyTitle = document.querySelector('.history-title');
    if (historyTitle) {
        historyTitle.textContent = `📊 ${STRATEGIES[strategy].displayName}`;
    }
    
    // Reload history with new strategy
    updateHistoryTable();
}

function startAutoRefresh() {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
    }
    
    autoRefreshInterval = setInterval(() => {
        fetchAllIndices();
    }, AUTO_REFRESH_SECONDS * 1000);
}

// ========================================
// SMC SETUPS TRACKING (STRATEGY-AWARE)
// ========================================

function getStrategyTable(strategy = null) {
    // Retorna la tabla correspondiente a cada estrategia
    const strat = strategy || currentStrategy;
    return STRATEGIES[strat]?.table || 'smc_m15_setups';
}

async function getAllActiveSetups(symbol) {
    // Get all setups with estado ACTIVA, EN_ZONA, PROFIT, PAUSADA, or TP (not yet released) for this symbol
    const table = getStrategyTable();
    const url = `${SUPABASE_URL}/rest/v1/${table}?symbol=eq.${encodeURIComponent(symbol)}&estado=in.(ACTIVA,EN_ZONA,PROFIT,PAUSADA,TP)&order=created_at.desc`;

    const response = await fetch(url, {
        method: 'GET',
        headers: {
            'apikey': SUPABASE_ANON_KEY,
            'Authorization': `Bearer ${SUPABASE_ANON_KEY}`,
            'Content-Type': 'application/json'
        }
    });
    
    if (!response.ok) {
        throw new Error(`Error HTTP: ${response.status}`);
    }
    
    const data = await response.json();
    
    // Filter out TP setups that have been released
    return data.filter(setup => {
        if (setup.estado === 'ACTIVA' || setup.estado === 'EN_ZONA' || setup.estado === 'PROFIT' || setup.estado === 'PAUSADA') {
            return true;
        }
        if (setup.estado === 'TP') {
            // Only include TP if it hasn't been released yet
            const isReleased = setup.motivo_cierre && setup.motivo_cierre.includes('liberada');
            return !isReleased;
        }
        return false;
    });
}

async function getAllSetupsForMatching(symbol) {
    // Get ALL setups for this symbol to check for duplicates (including closed/discarded ones)
    // This is used to prevent duplicate zone creation
    const table = getStrategyTable();
    const url = `${SUPABASE_URL}/rest/v1/${table}?symbol=eq.${encodeURIComponent(symbol)}&order=created_at.desc`;

    const response = await fetch(url, {
        method: 'GET',
        headers: {
            'apikey': SUPABASE_ANON_KEY,
            'Authorization': `Bearer ${SUPABASE_ANON_KEY}`,
            'Content-Type': 'application/json'
        }
    });
    
    if (!response.ok) {
        throw new Error(`Error HTTP: ${response.status}`);
    }
    
    return await response.json();
}

async function createSetup(setupData) {
    const table = getStrategyTable();
    const url = `${SUPABASE_URL}/rest/v1/${table}`;
    
    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'apikey': SUPABASE_ANON_KEY,
            'Authorization': `Bearer ${SUPABASE_ANON_KEY}`,
            'Content-Type': 'application/json',
            'Prefer': 'return=representation'
        },
        body: JSON.stringify(setupData)
    });
    
    if (!response.ok) {
        throw new Error(`Error HTTP: ${response.status}`);
    }
    
    return await response.json();
}

async function updateSetup(id, updateData, explicitTable = null) {
    // If explicitTable is provided, use it; otherwise fall back to currentStrategy
    const table = explicitTable || getStrategyTable();
    const url = `${SUPABASE_URL}/rest/v1/${table}?id=eq.${id}`;
    
    const response = await fetch(url, {
        method: 'PATCH',
        headers: {
            'apikey': SUPABASE_ANON_KEY,
            'Authorization': `Bearer ${SUPABASE_ANON_KEY}`,
            'Content-Type': 'application/json',
            'Prefer': 'return=representation'
        },
        body: JSON.stringify(updateData)
    });
    
    if (!response.ok) {
        throw new Error(`Error HTTP: ${response.status}`);
    }
    
    return await response.json();
}

async function closeSetup(id, motivo, explicitTable = null) {
    return await updateSetup(id, {
        estado: 'DESCARTADA',
        fecha_cierre: new Date().toISOString(),
        motivo_cierre: motivo
    }, explicitTable);
}

async function getSetupEnZonaOrProfit(symbol) {
    // Get the most recent EN_ZONA, PROFIT, or TP (not yet released) setup for this symbol
    const table = getStrategyTable();
    const url = `${SUPABASE_URL}/rest/v1/${table}?symbol=eq.${encodeURIComponent(symbol)}&estado=in.(EN_ZONA,PROFIT,TP)&order=created_at.desc&limit=5`;
    
    try {
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'apikey': SUPABASE_ANON_KEY,
                'Authorization': `Bearer ${SUPABASE_ANON_KEY}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            console.error(`Error fetching EN_ZONA/PROFIT/TP setup for ${symbol}: ${response.status}`);
            return null;
        }
        
        const data = await response.json();
        
        // Filter out TP setups that have been released
        const activeSetup = data.find(setup => {
            if (setup.estado === 'EN_ZONA' || setup.estado === 'PROFIT') {
                return true;
            }
            if (setup.estado === 'TP') {
                // Only include TP if it hasn't been released yet
                const isReleased = setup.motivo_cierre && setup.motivo_cierre.includes('liberada');
                return !isReleased;
            }
            return false;
        });
        
        return activeSetup || null;
    } catch (error) {
        console.error(`Error fetching EN_ZONA/PROFIT/TP setup for ${symbol}:`, error);
        return null;
    }
}

/**
 * Extract ultimo_evento_m15 from analysis
 * Helper function to reduce code duplication
 */
function getUltimoEventoM15(analysis) {
    if (analysis && analysis.smc && analysis.smc.eventosM15 && analysis.smc.eventosM15.length > 0) {
        const lastEvent = analysis.smc.eventosM15[analysis.smc.eventosM15.length - 1];
        return lastEvent?.evento || null;
    }
    return null;
}

/**
 * Reevaluate a PAUSADA zone to determine if it should be discarded or remain paused
 * 
 * @param {Object} setup - The zone setup to reevaluate
 * @param {Number} currentPrice - Current market price
 * @param {Object} analysis - SMC analysis data
 * @returns {String} - 'PAUSADA' or 'DESCARTADA'
 * 
 * ⚠️ IMPORTANTE - VALIDACIONES POR ESTRATEGIA:
 * 
 * SMC_M15_PRO:
 * - SOLO descarta si el precio toca SL
 * - NO descarta por cambios de Contexto H1
 * - NO descarta por cambios de Contexto M15
 * - NO descarta por cambios de Evento M15
 * - NO descarta por falta de confluencia (zona ya fue creada con confluencia inicial)
 * 
 * SMC_H1_M15_PRO:
 * - Descarta si el precio toca SL
 * - Descarta si Contexto H1 cambia contra la zona
 * - Descarta si Contexto M15 cambia contra la zona
 * - Descarta si Evento M15 deja de tener sentido
 * - Descarta si pierde confluencia mínima OB/FVG/Barrida
 * 
 * Note: Uses setup.strategy field to determine which validation rules to apply.
 */
async function reevaluatePausedZone(setup, currentPrice, analysis) {
    const updateData = {
        updated_at: new Date().toISOString()
    };
    
    // Determine which strategy this setup belongs to
    // Use setup.strategy if available, otherwise infer from setup properties
    // For SMC_M15_PRO: zones should only be discarded if price touches SL
    // For SMC_H1_M15_PRO: zones can be discarded for H1/M15 context changes too
    const setupStrategy = setup.strategy || 'SMC_M15_PRO'; // Default to SMC_M15_PRO if not set
    const setupTable = STRATEGIES[setupStrategy]?.table || 'smc_m15_setups';
    
    let shouldDiscard = false;
    let discardReason = null;
    
    // 1. Check if price touched SL (applies to all strategies)
    if (setup.direccion === 'ALCISTA' && currentPrice < setup.sl_price) {
        shouldDiscard = true;
        discardReason = 'Precio tocó SL de zona pausada';
    } else if (setup.direccion === 'BAJISTA' && currentPrice > setup.sl_price) {
        shouldDiscard = true;
        discardReason = 'Precio tocó SL de zona pausada';
    }
    
    // 2. Check H1/M15 context compatibility (ONLY for SMC_H1_M15_PRO)
    // For SMC_M15_PRO, PAUSADA zones should NOT be discarded by H1/M15 context changes
    if (!shouldDiscard && setupStrategy === 'SMC_H1_M15_PRO' && analysis && analysis.smc) {
        const tendenciaH1 = analysis.smc.tendenciaH1;
        const tendenciaM15 = analysis.smc.tendenciaM15;
        
        // If trends changed against the zone direction, discard
        if (tendenciaH1 && tendenciaH1 !== setup.direccion) {
            shouldDiscard = true;
            discardReason = 'Contexto H1 cambió contra la zona';
        } else if (tendenciaM15 && tendenciaM15 !== setup.direccion) {
            shouldDiscard = true;
            discardReason = 'Contexto M15 cambió contra la zona';
        }
    }
    
    // 3. Check if M15 event still makes sense (ONLY for SMC_H1_M15_PRO)
    // For SMC_M15_PRO, PAUSADA zones should NOT be discarded by M15 event changes
    if (!shouldDiscard && setupStrategy === 'SMC_H1_M15_PRO') {
        const ultimoEvento = getUltimoEventoM15(analysis);
        if (ultimoEvento) {
            const lastEventDireccion = ultimoEvento.includes('ALCISTA') ? 'ALCISTA' : 'BAJISTA';
            
            // If last event direction is opposite to zone direction, it may invalidate the zone
            if (lastEventDireccion !== setup.direccion) {
                shouldDiscard = true;
                discardReason = 'Evento M15 dejó de tener sentido para la zona';
            }
        }
    }
    
    // 4. Check minimum confluence (at least one of OB, FVG, or Barrida must be present)
    // This only applies to SMC_H1_M15_PRO
    // For SMC_M15_PRO, zones were already created with initial confluence, so we don't revalidate it
    if (!shouldDiscard && setupStrategy === 'SMC_H1_M15_PRO') {
        const hasConfluence = setup.ob || setup.fvg || setup.barrida;
        if (!hasConfluence) {
            shouldDiscard = true;
            discardReason = 'Zona no tiene confluencia OB/FVG/Barrida mínima';
        }
    }
    
    // If zone should be discarded, update it using the correct table
    if (shouldDiscard) {
        updateData.estado = 'DESCARTADA';
        updateData.fecha_cierre = new Date().toISOString();
        updateData.motivo_cierre = discardReason;
        await updateSetup(setup.id, updateData, setupTable);
        console.log(`✓ Zona PAUSADA ${setup.id} → DESCARTADA: ${discardReason} para ${setup.symbol} (estrategia: ${setupStrategy})`);
        return 'DESCARTADA';
    }
    
    // Zone remains PAUSADA (no log to avoid cluttering console)
    return 'PAUSADA';
}

/**
 * Check and update setup state based on price movements
 * Handles transitions: ACTIVA → EN_ZONA ⇄ PROFIT → TP (1:1) → [1:2 or SL return] → LIBERAR
 * PAUSADA zones are skipped from normal state updates (they are reevaluated separately)
 */
async function updateSetupState(setup, currentPrice, analysis = null) {
    // Skip PAUSADA zones - they are reevaluated separately
    if (setup.estado === 'PAUSADA') {
        return false;
    }
    
    const updateData = {
        updated_at: new Date().toISOString()
    };
    
    const isInZone = currentPrice >= setup.zona_desde && currentPrice <= setup.zona_hasta;
    const zona_size_puntos = Math.abs(setup.zona_hasta - setup.zona_desde);
    
    // Calculate TP 1:1, TP 1:2, and SL if not set yet
    if (setup.tp_price === null || setup.sl_price === null) {
        if (setup.direccion === 'ALCISTA') {
            updateData.tp_price = setup.zona_hasta + zona_size_puntos; // TP 1:1
            updateData.sl_price = setup.zona_desde;
        } else { // BAJISTA
            updateData.tp_price = setup.zona_desde - zona_size_puntos; // TP 1:1
            updateData.sl_price = setup.zona_hasta;
        }
        updateData.ratio_rr = 1.0;
    }
    
    const tp_1_1 = updateData.tp_price || setup.tp_price;
    const sl_price = updateData.sl_price || setup.sl_price;
    
    // Calculate TP 1:2
    let tp_1_2;
    if (setup.direccion === 'ALCISTA') {
        tp_1_2 = setup.zona_hasta + (zona_size_puntos * 2);
    } else {
        tp_1_2 = setup.zona_desde - (zona_size_puntos * 2);
    }
    
    // State transition logic
    if (setup.estado === 'TP') {
        // Already at TP 1:1, check for release conditions
        // A) Check if price reaches TP 1:2
        if (setup.direccion === 'ALCISTA' && currentPrice >= tp_1_2) {
            updateData.motivo_cierre = 'TP 1:2 alcanzado - zona liberada';
            // Keep estado as TP, just update motivo_cierre
            // The dashboard will check this motivo to release the zone
            console.log(`✓ Setup ${setup.id} reached TP 1:2 - zone released for ${setup.symbol}`);
        }
        else if (setup.direccion === 'BAJISTA' && currentPrice <= tp_1_2) {
            updateData.motivo_cierre = 'TP 1:2 alcanzado - zona liberada';
            console.log(`✓ Setup ${setup.id} reached TP 1:2 - zone released for ${setup.symbol}`);
        }
        // B) Check if price returns and crosses original SL after TP 1:1
        else if (setup.direccion === 'ALCISTA' && currentPrice < sl_price) {
            updateData.motivo_cierre = 'Precio volvió bajo SL original después de TP 1:1 - zona liberada';
            console.log(`✓ Setup ${setup.id} returned below SL after TP 1:1 - zone released for ${setup.symbol}`);
        }
        else if (setup.direccion === 'BAJISTA' && currentPrice > sl_price) {
            updateData.motivo_cierre = 'Precio volvió sobre SL original después de TP 1:1 - zona liberada';
            console.log(`✓ Setup ${setup.id} returned above SL after TP 1:1 - zone released for ${setup.symbol}`);
        }
    }
    // ⚠️ CRITICAL RULE: If price is in zone, state MUST be EN_ZONA (unless TP or SL state)
    // This ensures dynamic behavior: EN_ZONA ⇄ PROFIT (reversible transition)
    else if (isInZone && setup.estado !== 'SL') {
        // Price is back in zone - force EN_ZONA state (reversible from PROFIT)
        if (setup.estado !== 'EN_ZONA') {
            updateData.estado = 'EN_ZONA';
            console.log(`✓ Setup ${setup.id} returned to zone: ${setup.estado} → EN_ZONA for ${setup.symbol}`);
        }
    }
    // If NOT in zone, proceed with normal state logic
    else if (setup.estado === 'ACTIVA') {
        // ACTIVA → EN_ZONA: Price enters the zone
        if (isInZone) {
            updateData.estado = 'EN_ZONA';
            console.log(`✓ Setup ${setup.id} transitioned ACTIVA → EN_ZONA for ${setup.symbol}`);
        }
    } 
    else if (setup.estado === 'EN_ZONA') {
        // Check for SL hit first (highest priority) - only BEFORE TP 1:1
        if (setup.direccion === 'ALCISTA' && currentPrice < setup.zona_desde) {
            // ALCISTA: Price below zone = SL
            updateData.estado = 'SL';
            updateData.resultado_puntos = -zona_size_puntos;
            updateData.fecha_cierre = new Date().toISOString();
            updateData.motivo_cierre = 'Stop Loss alcanzado';
            console.log(`✓ Setup ${setup.id} transitioned EN_ZONA → SL for ${setup.symbol}`);
        }
        else if (setup.direccion === 'BAJISTA' && currentPrice > setup.zona_hasta) {
            // BAJISTA: Price above zone = SL
            updateData.estado = 'SL';
            updateData.resultado_puntos = -zona_size_puntos;
            updateData.fecha_cierre = new Date().toISOString();
            updateData.motivo_cierre = 'Stop Loss alcanzado';
            console.log(`✓ Setup ${setup.id} transitioned EN_ZONA → SL for ${setup.symbol}`);
        }
        // EN_ZONA → PROFIT: Price moves favorably but hasn't reached TP 1:1 yet
        else if (setup.direccion === 'ALCISTA' && currentPrice > setup.zona_hasta && currentPrice < tp_1_1) {
            updateData.estado = 'PROFIT';
            console.log(`✓ Setup ${setup.id} transitioned EN_ZONA → PROFIT for ${setup.symbol}`);
        }
        else if (setup.direccion === 'BAJISTA' && currentPrice < setup.zona_desde && currentPrice > tp_1_1) {
            updateData.estado = 'PROFIT';
            console.log(`✓ Setup ${setup.id} transitioned EN_ZONA → PROFIT for ${setup.symbol}`);
        }
        // EN_ZONA → TP: Price reaches TP 1:1 directly from zone
        else if (setup.direccion === 'ALCISTA' && currentPrice >= tp_1_1) {
            updateData.estado = 'TP';
            updateData.resultado_puntos = zona_size_puntos;
            updateData.fecha_cierre = new Date().toISOString();
            updateData.motivo_cierre = 'Take Profit 1:1 alcanzado';
            console.log(`✓ Setup ${setup.id} transitioned EN_ZONA → TP 1:1 for ${setup.symbol}`);
        }
        else if (setup.direccion === 'BAJISTA' && currentPrice <= tp_1_1) {
            updateData.estado = 'TP';
            updateData.resultado_puntos = zona_size_puntos;
            updateData.fecha_cierre = new Date().toISOString();
            updateData.motivo_cierre = 'Take Profit 1:1 alcanzado';
            console.log(`✓ Setup ${setup.id} transitioned EN_ZONA → TP 1:1 for ${setup.symbol}`);
        }
    }
    else if (setup.estado === 'PROFIT') {
        // Check for SL hit - only BEFORE TP 1:1
        if (setup.direccion === 'ALCISTA' && currentPrice < setup.zona_desde) {
            updateData.estado = 'SL';
            updateData.resultado_puntos = -zona_size_puntos;
            updateData.fecha_cierre = new Date().toISOString();
            updateData.motivo_cierre = 'Stop Loss alcanzado';
            console.log(`✓ Setup ${setup.id} transitioned PROFIT → SL for ${setup.symbol}`);
        }
        else if (setup.direccion === 'BAJISTA' && currentPrice > setup.zona_hasta) {
            updateData.estado = 'SL';
            updateData.resultado_puntos = -zona_size_puntos;
            updateData.fecha_cierre = new Date().toISOString();
            updateData.motivo_cierre = 'Stop Loss alcanzado';
            console.log(`✓ Setup ${setup.id} transitioned PROFIT → SL for ${setup.symbol}`);
        }
        // PROFIT → TP: Price reaches TP 1:1
        else if (setup.direccion === 'ALCISTA' && currentPrice >= tp_1_1) {
            updateData.estado = 'TP';
            updateData.resultado_puntos = zona_size_puntos;
            updateData.fecha_cierre = new Date().toISOString();
            updateData.motivo_cierre = 'Take Profit 1:1 alcanzado';
            console.log(`✓ Setup ${setup.id} transitioned PROFIT → TP 1:1 for ${setup.symbol}`);
        }
        else if (setup.direccion === 'BAJISTA' && currentPrice <= tp_1_1) {
            updateData.estado = 'TP';
            updateData.resultado_puntos = zona_size_puntos;
            updateData.fecha_cierre = new Date().toISOString();
            updateData.motivo_cierre = 'Take Profit 1:1 alcanzado';
            console.log(`✓ Setup ${setup.id} transitioned PROFIT → TP 1:1 for ${setup.symbol}`);
        }
    }
    
    // Calculate max_reaccion_puntos only for EN_ZONA or PROFIT states
    if (setup.estado === 'EN_ZONA' || setup.estado === 'PROFIT' || 
        (updateData.estado && (updateData.estado === 'EN_ZONA' || updateData.estado === 'PROFIT'))) {
        
        const currentEstado = updateData.estado || setup.estado;
        
        if (currentEstado === 'EN_ZONA' || currentEstado === 'PROFIT') {
            const distanceFromZone = setup.direccion === 'ALCISTA' 
                ? Math.max(0, currentPrice - setup.zona_hasta)
                : Math.max(0, setup.zona_desde - currentPrice);
            
            const currentMaxReaccion = setup.max_reaccion_puntos || 0;
            updateData.max_reaccion_puntos = Math.max(currentMaxReaccion, distanceFromZone);
        }
    }
    
    // Only update if there are meaningful changes
    const hasChanges = Object.keys(updateData).length > 1; // more than just updated_at
    if (hasChanges) {
        // Use the setup's strategy to determine the correct table
        const setupTable = setup.strategy ? STRATEGIES[setup.strategy]?.table : null;
        await updateSetup(setup.id, updateData, setupTable);
        
        // If transitioned to SL, check for paused zones to reactivate
        if (updateData.estado === 'SL') {
            await handleSLHitAndReactivatePausedZones(setup.symbol, currentPrice, analysis);
        }
        
        return true;
    }
    
    return false;
}

/**
 * Handle SL hit: reevaluate paused zones and reactivate the most proximate valid one
 */
async function handleSLHitAndReactivatePausedZones(symbol, currentPrice, analysis) {
    try {
        // Get all PAUSADA zones for this symbol
        const table = getStrategyTable();
        const url = `${SUPABASE_URL}/rest/v1/${table}?symbol=eq.${encodeURIComponent(symbol)}&estado=eq.PAUSADA&order=created_at.desc`;
        
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'apikey': SUPABASE_ANON_KEY,
                'Authorization': `Bearer ${SUPABASE_ANON_KEY}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            console.error(`Error fetching PAUSADA zones for ${symbol}: ${response.status}`);
            return;
        }
        
        const pausedZones = await response.json();
        
        if (pausedZones.length === 0) {
            console.log(`No hay zonas PAUSADAS para reactivar en ${symbol}`);
            return;
        }
        
        // Reevaluate each paused zone
        const validPausedZones = [];
        for (const zone of pausedZones) {
            const result = await reevaluatePausedZone(zone, currentPrice, analysis);
            if (result === 'PAUSADA') {
                validPausedZones.push(zone);
            }
        }
        
        if (validPausedZones.length === 0) {
            console.log(`No quedan zonas PAUSADAS válidas para reactivar en ${symbol}`);
            return;
        }
        
        // Find the zone closest to current price
        let closestZone = validPausedZones[0];
        let minDistance = calculateDistanceToZone(closestZone, currentPrice);
        
        for (let i = 1; i < validPausedZones.length; i++) {
            const distance = calculateDistanceToZone(validPausedZones[i], currentPrice);
            if (distance < minDistance) {
                minDistance = distance;
                closestZone = validPausedZones[i];
            }
        }
        
        // Reactivate the closest zone, using its correct table
        const closestZoneTable = closestZone.strategy ? STRATEGIES[closestZone.strategy]?.table : table;
        await updateSetup(closestZone.id, {
            estado: 'ACTIVA',
            updated_at: new Date().toISOString()
        }, closestZoneTable);
        console.log(`✓ Zona PAUSADA ${closestZone.id} → ACTIVA (reactivada tras SL) para ${symbol}`);
        
        // Update closestZone object with new estado before calling updateSetupState
        closestZone.estado = 'ACTIVA';
        
        // Immediately check if it should transition to EN_ZONA
        await updateSetupState(closestZone, currentPrice, analysis);
        
    } catch (error) {
        console.error(`Error handling SL hit and reactivating paused zones for ${symbol}:`, error);
    }
}

/**
 * Calculate distance from current price to a zone
 */
function calculateDistanceToZone(zone, currentPrice) {
    if (currentPrice >= zone.zona_desde && currentPrice <= zone.zona_hasta) {
        return 0; // Price is inside zone
    }
    
    return Math.min(
        Math.abs(currentPrice - zone.zona_desde),
        Math.abs(currentPrice - zone.zona_hasta)
    );
}

/**
 * Valida si una zona cumple con los requisitos de la estrategia H1+M15
 * Esta validación se aplica al CREAR el setup, no es un filtro visual
 * Boom: H1 ALCISTA + Evento M15 ALCISTA (CHOCH o BOS)
 * Crash: H1 BAJISTA + Evento M15 BAJISTA (CHOCH o BOS)
 */
function cumpleValidacionH1M15(symbol, tendenciaH1, eventoM15) {
    const tipoIndice = symbol.includes('Boom') ? 'Boom' : 'Crash';
    
    // Para Boom: H1 debe ser ALCISTA y evento M15 debe ser ALCISTA
    if (tipoIndice === 'Boom') {
        return tendenciaH1 === 'ALCISTA' && 
               (eventoM15.includes('CHOCH_ALCISTA') || eventoM15.includes('BOS_ALCISTA'));
    }
    
    // Para Crash: H1 debe ser BAJISTA y evento M15 debe ser BAJISTA
    if (tipoIndice === 'Crash') {
        return tendenciaH1 === 'BAJISTA' && 
               (eventoM15.includes('CHOCH_BAJISTA') || eventoM15.includes('BOS_BAJISTA'));
    }
    
    return false;
}

async function trackZoneHistory(symbol, analysis) {
    try {
        const zonaM15 = analysis.smc.zonaM15;
        const currentPrice = analysis.currentPrice;
        
        // SIN SETUP: If no valid zone exists, don't create or track anything
        if (!zonaM15 || !zonaM15.es_util) {
            // Get all active setups (including PAUSADA) to update their states based on price
            const existingSetups = await getAllActiveSetups(symbol);
            
            // Reevaluate PAUSADA zones
            for (const setup of existingSetups) {
                if (setup.estado === 'PAUSADA') {
                    await reevaluatePausedZone(setup, currentPrice, analysis);
                } else {
                    await updateSetupState(setup, currentPrice, analysis);
                }
            }
            
            return; // Don't create new records for SIN SETUP
        }
        
        // Get tipo_indice (Boom or Crash)
        const tipoIndice = symbol.includes('Boom') ? 'Boom' : 'Crash';
        
        // Get ultimo_evento_m15 from analysis for matching
        const ultimo_evento_m15 = getUltimoEventoM15(analysis);
        
        // If no valid evento is detected, we can't perform proper matching
        if (!ultimo_evento_m15) {
            console.warn(`⚠️ No se pudo obtener ultimo_evento_m15 para ${symbol}, omitiendo matching`);
            // Still update existing setups' states, but don't try to match/create
            const existingSetups = await getAllActiveSetups(symbol);
            for (const setup of existingSetups) {
                if (setup.estado === 'PAUSADA') {
                    await reevaluatePausedZone(setup, currentPrice, analysis);
                } else {
                    await updateSetupState(setup, currentPrice, analysis);
                }
            }
            return;
        }
        
        // Get all active/in-zone/profit/pausada/TP setups for this symbol (for state management)
        const activeSetups = await getAllActiveSetups(symbol);
        
        // Get ALL setups for this symbol (including closed/discarded) for duplicate checking
        const allSetups = await getAllSetupsForMatching(symbol);
        
        // Separate operative zones from paused zones
        // Operative: ACTIVA, EN_ZONA, PROFIT, TP (actively tracking price)
        // Paused: PAUSADA (valid but not currently operative)
        const operativeSetups = activeSetups.filter(s => 
            ['ACTIVA', 'EN_ZONA', 'PROFIT', 'TP'].includes(s.estado)
        );
        const pausedSetups = activeSetups.filter(s => s.estado === 'PAUSADA');
        
        // Reevaluate all PAUSADA zones first
        for (const setup of pausedSetups) {
            await reevaluatePausedZone(setup, currentPrice, analysis);
        }
        
        // Find the main operative zone (closest to price among ACTIVA/EN_ZONA/PROFIT)
        let mainOperativeZone = null;
        let minDistance = Infinity;
        
        for (const setup of operativeSetups) {
            if (setup.estado === 'ACTIVA' || setup.estado === 'EN_ZONA' || setup.estado === 'PROFIT') {
                const distance = calculateDistanceToZone(setup, currentPrice);
                if (distance < minDistance) {
                    minDistance = distance;
                    mainOperativeZone = setup;
                }
            }
        }
        
        // Check if dashboard is locked (any setup in EN_ZONA, PROFIT, or TP not yet released)
        const dashboardLocked = operativeSetups.some(setup => {
            if (setup.estado === 'EN_ZONA' || setup.estado === 'PROFIT') {
                return true;
            }
            // TP is locking unless it's been released (motivo_cierre contains "liberada")
            if (setup.estado === 'TP') {
                const isReleased = setup.motivo_cierre && setup.motivo_cierre.includes('liberada');
                return !isReleased; // Lock if NOT released
            }
            return false;
        });
        
        // Calculate new zone boundaries
        const newZonaDesde = zonaM15.zona_desde;
        const newZonaHasta = zonaM15.zona_hasta;
        const newZonaSize = Math.abs(newZonaHasta - newZonaDesde);
        
        // ⚠️ IMPORTANTE - PREVENCIÓN DE DUPLICADOS
        // NO permitir múltiples registros para la misma zona: (symbol + zona_desde + zona_hasta + evento)
        // Si ya existe: UPDATE estado en lugar de INSERT
        // 
        // MATCHING LOGIC: Find if this zone already exists
        // Matching criteria: symbol (implicit), zona_desde, zona_hasta, evento, direccion
        // Tolerance: 0.001 represents ~0.1% difference for typical Boom/Crash prices (~1000)
        // This handles floating-point precision and minor rounding differences
        const tolerance = 0.001;
        let matchingSetup = null;
        
        // First, check for exact match (same zone boundaries, evento, and direccion)
        for (const setup of allSetups) {
            const zonaDesdeMatch = Math.abs(setup.zona_desde - newZonaDesde) < tolerance;
            const zonaHastaMatch = Math.abs(setup.zona_hasta - newZonaHasta) < tolerance;
            const direccionMatch = setup.direccion === zonaM15.direccion;
            const eventoMatch = setup.evento === ultimo_evento_m15;
            
            if (zonaDesdeMatch && zonaHastaMatch && direccionMatch && eventoMatch) {
                matchingSetup = setup;
                console.log(`✓ Zona exacta encontrada (ID: ${setup.id}, estado: ${setup.estado}) para ${symbol}`);
                break;
            }
        }
        
        // If no exact match, check for containment or strong overlap (only with active/paused zones)
        // Note: Containment uses strict comparison (no tolerance) to ensure a zone is truly within another
        // This prevents incorrectly matching zones that are merely adjacent
        if (!matchingSetup) {
            for (const setup of activeSetups) {
                // Check if new zone is contained within existing zone (strict containment)
                const isContained = newZonaDesde >= setup.zona_desde && 
                                   newZonaHasta <= setup.zona_hasta;
                
                // Check for strong overlap (>= 70%)
                const overlap = Math.min(newZonaHasta, setup.zona_hasta) - Math.max(newZonaDesde, setup.zona_desde);
                const existingZonaSize = Math.abs(setup.zona_hasta - setup.zona_desde);
                const minSize = Math.min(newZonaSize, existingZonaSize);
                const overlapRatio = overlap > 0 ? overlap / minSize : 0;
                
                if ((isContained || overlapRatio >= 0.70) && setup.direccion === zonaM15.direccion) {
                    matchingSetup = setup;
                    console.log(`✓ Nueva zona ${isContained ? 'contenida' : 'solapa ' + (overlapRatio * 100).toFixed(1) + '%'} en setup existente ${setup.id} para ${symbol}`);
                    break;
                }
            }
        }
        
        // If we found a matching setup, update it instead of creating new
        if (matchingSetup) {
            const updateData = {
                updated_at: new Date().toISOString(),
                score: zonaM15.score,
                ob: zonaM15.ob ? true : false,
                fvg: zonaM15.fvg ? true : false,
                barrida: zonaM15.barrida ? true : false,
                evento: ultimo_evento_m15
            };
            
            // Update tendencias if they are missing (null or empty)
            if (!matchingSetup.tendencia_h1 && analysis.smc.tendenciaH1) {
                updateData.tendencia_h1 = analysis.smc.tendenciaH1;
            }
            if (!matchingSetup.tendencia_m15 && analysis.smc.tendenciaM15) {
                updateData.tendencia_m15 = analysis.smc.tendenciaM15;
            }
            
            // If matching zone is in a terminal state (DESCARTADA, SL, closed), reactivate it
            // Determine the appropriate estado based on dashboard lock status
            if (['DESCARTADA', 'SL', 'TP'].includes(matchingSetup.estado) && matchingSetup.fecha_cierre) {
                const shouldBePaused = dashboardLocked || mainOperativeZone;
                updateData.estado = shouldBePaused ? 'PAUSADA' : 'ACTIVA';
                updateData.fecha_cierre = null;
                updateData.motivo_cierre = null;
                console.log(`✓ Zona duplicada ${matchingSetup.id} reactivada desde ${matchingSetup.estado} → ${updateData.estado} para ${symbol}`);
            }
            
            // Use the matching setup's strategy to determine the correct table
            const matchingSetupTable = matchingSetup.strategy ? STRATEGIES[matchingSetup.strategy]?.table : null;
            await updateSetup(matchingSetup.id, updateData, matchingSetupTable);
            console.log(`✓ Setup ${matchingSetup.id} actualizado (mantiene zona original) para ${symbol}`);
            
            // Update state based on price movement (only if in an active state)
            if (ACTIVE_SETUP_STATES.includes(matchingSetup.estado) || 
                (updateData.estado && ACTIVE_SETUP_STATES.includes(updateData.estado))) {
                // Refresh matchingSetup with updated estado if it was changed
                if (updateData.estado) {
                    matchingSetup.estado = updateData.estado;
                }
                await updateSetupState(matchingSetup, currentPrice, analysis);
            }
        }
        // If zone doesn't exist, create a new setup
        else {
            
            // Calculate TP and SL for 1:1 ratio
            let tp_price, sl_price;
            if (zonaM15.direccion === 'ALCISTA') {
                tp_price = newZonaHasta + newZonaSize;
                sl_price = newZonaDesde;
            } else { // BAJISTA
                tp_price = newZonaDesde - newZonaSize;
                sl_price = newZonaHasta;
            }
            
            const newSetup = {
                symbol: symbol,
                tipo_indice: tipoIndice,
                direccion: zonaM15.direccion,
                zona_desde: newZonaDesde,
                zona_hasta: newZonaHasta,
                zona_size_puntos: newZonaSize,
                precio_actual_detectado: currentPrice,
                precio_entrada_referencia: zonaM15.direccion === 'ALCISTA' ? newZonaHasta : newZonaDesde,
                score: zonaM15.score,
                evento: ultimo_evento_m15,
                ob: zonaM15.ob ? true : false,
                fvg: zonaM15.fvg ? true : false,
                barrida: zonaM15.barrida ? true : false,
                tendencia_h1: analysis.smc.tendenciaH1 || null,
                tendencia_m15: analysis.smc.tendenciaM15 || null,
                tp_price: tp_price,
                sl_price: sl_price,
                ratio_rr: 1.0,
                max_reaccion_puntos: null,
                resultado_puntos: null,
                fecha_cierre: null,
                motivo_cierre: null,
                strategy: currentStrategy  // Store which strategy created this setup
            };
            
            // VALIDACIÓN H1+M15: Si estamos en estrategia H1+M15, validar antes de determinar el estado
            let estadoInicial;
            if (currentStrategy === 'SMC_H1_M15_PRO') {
                // Validar H1+M15
                const cumpleH1M15 = cumpleValidacionH1M15(
                    symbol, 
                    analysis.smc.tendenciaH1 || '--', 
                    ultimo_evento_m15
                );
                
                if (!cumpleH1M15) {
                    // No cumple validación → DESCARTADA
                    const tipoIndice = symbol.includes('Boom') ? 'Boom' : 'Crash';
                    const razonDescarte = tipoIndice === 'Boom'
                        ? `NO CUMPLE H1+M15: Se requiere H1 ALCISTA + M15 ALCISTA (actual: H1=${analysis.smc.tendenciaH1 || '--'}, M15=${ultimo_evento_m15})`
                        : `NO CUMPLE H1+M15: Se requiere H1 BAJISTA + M15 BAJISTA (actual: H1=${analysis.smc.tendenciaH1 || '--'}, M15=${ultimo_evento_m15})`;
                    
                    newSetup.estado = 'DESCARTADA';
                    newSetup.motivo_cierre = razonDescarte;
                    newSetup.fecha_cierre = new Date().toISOString();
                    
                    const created = await createSetup(newSetup);
                    console.log(`✓ Zona DESCARTADA por no cumplir H1+M15 para ${symbol}: ${razonDescarte}`);
                    return; // No continuar con lógica de zona operativa
                }
                
                // Cumple validación → continuar normalmente
                estadoInicial = dashboardLocked || mainOperativeZone ? 'PAUSADA' : 'ACTIVA';
            } else {
                // SMC M15 PRO: No aplicar validación H1+M15
                estadoInicial = dashboardLocked || mainOperativeZone ? 'PAUSADA' : 'ACTIVA';
            }
            
            // Determine if this should be the operative zone or a paused zone
            newSetup.estado = estadoInicial;
            
            if (estadoInicial === 'PAUSADA') {
                // Dashboard is locked or there's already an operative zone
                // Create this as PAUSADA
                const created = await createSetup(newSetup);
                console.log(`✓ Nueva zona PAUSADA creada para ${symbol} (TP: ${tp_price}, SL: ${sl_price})`);
            } else {
                // No operative zone yet, create as ACTIVA
                const created = await createSetup(newSetup);
                console.log(`✓ Nuevo setup ACTIVO creado para ${symbol} (TP: ${tp_price}, SL: ${sl_price})`);
                
                // Check if it should immediately transition to EN_ZONA
                if (created && created.length > 0) {
                    await updateSetupState(created[0], currentPrice, analysis);
                }
            }
        }
        
        // Update all operative setups (state transitions)
        for (const setup of operativeSetups) {
            // Skip the matching setup as we already updated it above
            if (matchingSetup && setup.id === matchingSetup.id) {
                continue;
            }
            
            // Update state based on current price
            await updateSetupState(setup, currentPrice, analysis);
        }
        
        // After all updates, ensure only one operative zone remains
        await ensureSingleOperativeZone(symbol, currentPrice, analysis);
        
    } catch (error) {
        console.error(`Error tracking zone history for ${symbol}:`, error);
    }
}

/**
 * Ensure there is only one operative zone (ACTIVA, EN_ZONA, or PROFIT) per symbol
 * If multiple exist, keep the closest to current price and pause the rest
 */
async function ensureSingleOperativeZone(symbol, currentPrice, analysis) {
    try {
        // Get all operative zones (ACTIVA, EN_ZONA, PROFIT) for this symbol from current strategy
        const table = getStrategyTable();
        const url = `${SUPABASE_URL}/rest/v1/${table}?symbol=eq.${encodeURIComponent(symbol)}&estado=in.(ACTIVA,EN_ZONA,PROFIT)&order=created_at.desc`;
        
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'apikey': SUPABASE_ANON_KEY,
                'Authorization': `Bearer ${SUPABASE_ANON_KEY}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            console.error(`Error fetching operative zones for ${symbol}: ${response.status}`);
            return;
        }
        
        const operativeZones = await response.json();
        
        if (operativeZones.length <= 1) {
            return; // Only one or no operative zone, nothing to do
        }
        
        // Find the zone closest to current price
        let closestZone = operativeZones[0];
        let minDistance = calculateDistanceToZone(closestZone, currentPrice);
        
        for (let i = 1; i < operativeZones.length; i++) {
            const distance = calculateDistanceToZone(operativeZones[i], currentPrice);
            if (distance < minDistance) {
                minDistance = distance;
                closestZone = operativeZones[i];
            }
        }
        
        // Pause all other zones, using the correct table based on their strategy
        for (const zone of operativeZones) {
            if (zone.id !== closestZone.id) {
                const zoneTable = zone.strategy ? STRATEGIES[zone.strategy]?.table : table;
                await updateSetup(zone.id, {
                    estado: 'PAUSADA',
                    updated_at: new Date().toISOString()
                }, zoneTable);
                console.log(`✓ Zona ${zone.id} → PAUSADA (no es la más próxima) para ${symbol}`);
            }
        }
        
    } catch (error) {
        console.error(`Error ensuring single operative zone for ${symbol}:`, error);
    }
}

async function fetchAllIndices() {
    updateLastUpdateTime();
    
    const allSymbols = [...ALL_INDICES.boom, ...ALL_INDICES.crash];
    const results = {};
    
    // Fetch data for all indices in parallel
    for (const symbol of allSymbols) {
        try {
            const analysis = await fetchAndAnalyzeSymbol(symbol);
            results[symbol] = analysis;
            
            // Track zone history to smc_m15_setups
            // (getStrategyTable always returns smc_m15_setups now)
            if (analysis && !analysis.error) {
                await trackZoneHistory(symbol, analysis);
            }
        } catch (error) {
            console.error(`Error fetching ${symbol}:`, error);
            results[symbol] = {
                error: true,
                message: error.message
            };
        }
    }
    
    // Update tables
    await updateBoomTable(results);
    await updateCrashTable(results);
    
    // Don't update history table here - only when user navigates to history view
}

async function fetchAndAnalyzeSymbol(symbol) {
    // Fetch multiple timeframes
    const [candlesH1, candlesM15, candlesM1] = await Promise.all([
        fetchCandles(symbol, 'H1', 500),
        fetchCandles(symbol, 'M15', 800),
        fetchCandles(symbol, 'M1', 600)
    ]);
    
    if (!candlesM15 || candlesM15.length === 0) {
        return {
            error: true,
            message: 'No hay datos M15'
        };
    }
    
    // Debug logging for Boom 1000 Index
    if (symbol === 'Boom 1000 Index') {
        console.log('========================================');
        console.log('DEBUG BOOM 1000 INDEX - fetchAndAnalyzeSymbol');
        console.log('========================================');
        
        // Timestamps and quantities
        if (candlesH1 && candlesH1.length > 0) {
            console.log('H1 Candles:');
            console.log('  Cantidad:', candlesH1.length);
            console.log('  Primera vela timestamp:', candlesH1[0].timestamp);
            console.log('  Última vela timestamp:', candlesH1[candlesH1.length - 1].timestamp);
        }
        
        if (candlesM15 && candlesM15.length > 0) {
            console.log('M15 Candles:');
            console.log('  Cantidad:', candlesM15.length);
            console.log('  Primera vela timestamp:', candlesM15[0].timestamp);
            console.log('  Última vela timestamp:', candlesM15[candlesM15.length - 1].timestamp);
        }
        
        if (candlesM1 && candlesM1.length > 0) {
            console.log('M1 Candles:');
            console.log('  Cantidad:', candlesM1.length);
            console.log('  Primera vela timestamp:', candlesM1[0].timestamp);
            console.log('  Última vela timestamp:', candlesM1[candlesM1.length - 1].timestamp);
        }
    }
    
    // Perform SMC analysis
    const smcResult = analyzeSMC(candlesH1, candlesM15, candlesM1, symbol);
    
    // Get current price
    const currentPrice = candlesM15[candlesM15.length - 1].close;
    const timestamp = candlesM15[candlesM15.length - 1].timestamp;
    
    // Debug logging for Boom 1000 Index - SMC Results
    if (symbol === 'Boom 1000 Index') {
        console.log('Precio Actual:', currentPrice);
        console.log('');
        
        // Last M15 event used for zone
        if (smcResult.eventosM15 && smcResult.eventosM15.length > 0) {
            const lastEvent = smcResult.eventosM15[smcResult.eventosM15.length - 1];
            console.log('Último evento M15 (general):');
            console.log('  Tipo:', lastEvent.evento);
            console.log('  Index:', lastEvent.index);
            console.log('  Timestamp:', lastEvent.timestamp);
            console.log('  Nivel roto:', lastEvent.nivel_roto);
        }
        
        // Final M15 zone
        if (smcResult.zonaM15) {
            console.log('');
            console.log('Zona M15 Final:');
            console.log('  Dirección:', smcResult.zonaM15.direccion);
            console.log('  Zona desde:', smcResult.zonaM15.zona_desde);
            console.log('  Zona hasta:', smcResult.zonaM15.zona_hasta);
            console.log('  Score:', smcResult.zonaM15.score);
            console.log('  Es útil:', smcResult.zonaM15.es_util);
            console.log('  Motivo:', smcResult.zonaM15.motivo);
            console.log('  Dirección operativa:', smcResult.zonaM15.direccion_operativa);
            console.log('');
            console.log('Evento M15 usado para zona:');
            console.log('  Tipo:', smcResult.zonaM15.evento.evento);
            console.log('  Index:', smcResult.zonaM15.debug_evento_usado_index);
            console.log('  Timestamp:', smcResult.zonaM15.debug_evento_usado_timestamp);
            console.log('  Nivel roto:', smcResult.zonaM15.evento.nivel_roto);
            
            // OB used
            console.log('');
            if (smcResult.zonaM15.ob) {
                console.log('OB usado:');
                console.log('  Tipo:', smcResult.zonaM15.ob.tipo);
                console.log('  Desde:', smcResult.zonaM15.ob.desde);
                console.log('  Hasta:', smcResult.zonaM15.ob.hasta);
                console.log('  Timestamp:', smcResult.zonaM15.ob.timestamp);
            } else {
                console.log('OB usado: NO');
            }
            
            // FVG used
            console.log('');
            if (smcResult.zonaM15.fvg) {
                console.log('FVG usado:');
                console.log('  Tipo:', smcResult.zonaM15.fvg.tipo);
                console.log('  Desde:', smcResult.zonaM15.fvg.desde);
                console.log('  Hasta:', smcResult.zonaM15.fvg.hasta);
                console.log('  Index:', smcResult.zonaM15.fvg.index);
                console.log('  Timestamp:', smcResult.zonaM15.fvg.timestamp);
            } else {
                console.log('FVG usado: NO');
            }
            
            // Barrida used
            console.log('');
            if (smcResult.zonaM15.barrida) {
                console.log('Barrida usada:');
                console.log('  Tipo:', smcResult.zonaM15.barrida.tipo);
                console.log('  Nivel:', smcResult.zonaM15.barrida.nivel);
                console.log('  Timestamp:', smcResult.zonaM15.barrida.timestamp);
                if (smcResult.zonaM15.barrida.low !== undefined) {
                    console.log('  Low:', smcResult.zonaM15.barrida.low);
                }
                if (smcResult.zonaM15.barrida.high !== undefined) {
                    console.log('  High:', smcResult.zonaM15.barrida.high);
                }
                console.log('  Close:', smcResult.zonaM15.barrida.close);
            } else {
                console.log('Barrida usada: NO');
            }
        } else {
            console.log('');
            console.log('Zona M15 Final: NO SE CREÓ');
        }
        
        // M1 zone info
        if (smcResult.zonaM1) {
            console.log('');
            console.log('Zona M1:');
            console.log('  Desde:', smcResult.zonaM1.zona_m1_desde);
            console.log('  Hasta:', smcResult.zonaM1.zona_m1_hasta);
            console.log('  Confirmación:', smcResult.zonaM1.m1_confirmacion);
            console.log('  Velas M1 usadas:', smcResult.zonaM1.velas_m1_usadas);
            console.log('  Precio dentro M1:', smcResult.zonaM1.precio_dentro_m1);
        }
        
        console.log('========================================');
        console.log('');
    }
    
    return {
        symbol,
        currentPrice,
        timestamp,
        smc: smcResult
    };
}

async function fetchCandles(symbol, timeframe, limit) {
    const url = `${SUPABASE_URL}/rest/v1/market_candles?symbol=eq.${encodeURIComponent(symbol)}&timeframe=eq.${timeframe}&order=timestamp.desc&limit=${limit}`;
    
    const response = await fetch(url, {
        method: 'GET',
        headers: {
            'apikey': SUPABASE_ANON_KEY,
            'Authorization': `Bearer ${SUPABASE_ANON_KEY}`,
            'Content-Type': 'application/json'
        }
    });
    
    if (!response.ok) {
        throw new Error(`Error HTTP: ${response.status}`);
    }
    
    const data = await response.json();
    return data.reverse();
}

async function updateBoomTable(results) {
    const tbody = document.getElementById('boomTableBody');
    tbody.innerHTML = '';
    
    for (const symbol of ALL_INDICES.boom) {
        const row = await createTableRow(symbol, results[symbol]);
        tbody.appendChild(row);
    }
}

async function updateCrashTable(results) {
    const tbody = document.getElementById('crashTableBody');
    tbody.innerHTML = '';
    
    for (const symbol of ALL_INDICES.crash) {
        const row = await createTableRow(symbol, results[symbol]);
        tbody.appendChild(row);
    }
}

async function createTableRow(symbol, data) {
    const tr = document.createElement('tr');
    
    if (!data || data.error) {
        tr.innerHTML = `
            <td class="index-name">${symbol}</td>
            <td colspan="11" class="loading">${data ? data.message : 'Cargando...'}</td>
        `;
        return tr;
    }
    
    const smc = data.smc;
    
    // Check for existing EN_ZONA, PROFIT, or TP (not yet released) setup
    const setupEnZonaOrProfit = await getSetupEnZonaOrProfit(symbol);
    
    // Decide which data source to use for display
    let displayZonaDesde, displayZonaHasta, displayDireccion, displayScore, displayOB, displayFVG, displayBarrida, displayEstado;
    
    // Determine if there's a valid zone
    const hasValidZone = smc.zonaM15 && smc.zonaM15.es_util;
    
    if (setupEnZonaOrProfit) {
        // Use EN_ZONA, PROFIT, or TP setup data for display
        displayDireccion = setupEnZonaOrProfit.direccion;
        
        // Handle estado display - check if TP is waiting for release
        if (setupEnZonaOrProfit.estado === 'TP') {
            const isReleased = setupEnZonaOrProfit.motivo_cierre && setupEnZonaOrProfit.motivo_cierre.includes('liberada');
            if (!isReleased) {
                // TP reached 1:1 but not yet released - show ESPERANDO_ACOMODO
                displayEstado = 'ESPERANDO_ACOMODO';
                // Don't show zone info when ESPERANDO_ACOMODO
                displayZonaDesde = null;
                displayZonaHasta = null;
                displayScore = 0;
                displayOB = false;
                displayFVG = false;
                displayBarrida = false;
            } else {
                // TP released - this shouldn't appear in dashboard, but handle it anyway
                displayEstado = setupEnZonaOrProfit.estado;
                displayZonaDesde = setupEnZonaOrProfit.zona_desde;
                displayZonaHasta = setupEnZonaOrProfit.zona_hasta;
                displayScore = setupEnZonaOrProfit.score;
                displayOB = setupEnZonaOrProfit.ob;
                displayFVG = setupEnZonaOrProfit.fvg;
                displayBarrida = setupEnZonaOrProfit.barrida;
            }
        } else {
            // EN_ZONA, PROFIT, or ACTIVA - show zone info normally
            displayEstado = setupEnZonaOrProfit.estado;
            displayZonaDesde = setupEnZonaOrProfit.zona_desde;
            displayZonaHasta = setupEnZonaOrProfit.zona_hasta;
            displayScore = setupEnZonaOrProfit.score;
            displayOB = setupEnZonaOrProfit.ob;
            displayFVG = setupEnZonaOrProfit.fvg;
            displayBarrida = setupEnZonaOrProfit.barrida;
        }
    } else if (!hasValidZone) {
        // Part 1: SIN SETUP - No valid zone available
        displayZonaDesde = null;
        displayZonaHasta = null;
        displayDireccion = smc.direccionOperativa || '--';
        displayScore = 0;
        displayOB = false;
        displayFVG = false;
        displayBarrida = false;
        displayEstado = 'SIN_SETUP';
    } else {
        // Use current analysis data (new zone detected, not yet in history)
        displayZonaDesde = smc.zonaM15.zona_desde;
        displayZonaHasta = smc.zonaM15.zona_hasta;
        displayDireccion = smc.direccionOperativa || '--';
        displayScore = smc.zonaM15.score;
        displayOB = smc.zonaM15.ob ? true : false;
        displayFVG = smc.zonaM15.fvg ? true : false;
        displayBarrida = smc.zonaM15.barrida ? true : false;
        displayEstado = 'ACTIVA'; // New zone, not yet tracked
    }
    
    // Get last event M15
    let lastEventM15 = '--';
    if (smc.eventosM15 && smc.eventosM15.length > 0) {
        const evento = smc.eventosM15[smc.eventosM15.length - 1];
        lastEventM15 = `${evento.evento}`;
    }
    
    // Zone M15 with individual boxes
    let zonaM15HTML = '<span class="zone-cell">--</span>';
    if (displayZonaDesde !== null && displayZonaHasta !== null && displayEstado !== 'ESPERANDO_ACOMODO') {
        zonaM15HTML = `
            <div class="zone-boxes">
                <div class="zone-price-row">
                    <span class="zone-label">Desde:</span>
                    <span class="zone-price">${formatPrice(displayZonaDesde)}</span>
                    <button class="copy-btn" onclick="copyToClipboard('${displayZonaDesde}', this)">📋</button>
                </div>
                <div class="zone-price-row">
                    <span class="zone-label">Hasta:</span>
                    <span class="zone-price">${formatPrice(displayZonaHasta)}</span>
                    <button class="copy-btn" onclick="copyToClipboard('${displayZonaHasta}', this)">📋</button>
                </div>
            </div>
        `;
    } else if (displayEstado === 'ESPERANDO_ACOMODO') {
        zonaM15HTML = '<span class="zone-cell zona-esperando">Esperando...</span>';
    }
    
    // Score
    const score = displayScore;
    let scoreClass = 'score-low';
    if (score >= 8) scoreClass = 'score-high';
    else if (score >= 5) scoreClass = 'score-medium';
    
    // OB, FVG, Barrida - show NO for SIN_SETUP and ESPERANDO_ACOMODO
    const ob = displayOB ? 'SÍ' : 'NO';
    const fvg = displayFVG ? 'SÍ' : 'NO';
    const barrida = displayBarrida ? 'SÍ' : 'NO';
    
    // Estado
    let estadoText = displayEstado;
    let estadoClass = 'status-badge ';
    if (estadoText === 'ACTIVA') {
        estadoClass += 'status-activa';
        estadoText = 'ACTIVA';
    } else if (estadoText === 'EN_ZONA' || estadoText.includes('DENTRO')) {
        estadoClass += 'status-esperando';
        estadoText = 'EN ZONA';
    } else if (estadoText === 'PROFIT') {
        estadoClass += 'status-profit';
        estadoText = 'PROFIT';
    } else if (estadoText === 'PAUSADA') {
        estadoClass += 'status-pausada';
        estadoText = 'PAUSADA';
    } else if (estadoText === 'ESPERANDO_ACOMODO') {
        estadoClass += 'status-esperando-acomodo';
        estadoText = 'ESPERANDO ACOMODO';
    } else if (estadoText === 'SIN_SETUP') {
        estadoClass += 'status-sin-setup';
        estadoText = 'SIN SETUP';
    } else if (estadoText === 'NO_CUMPLE_H1M15') {
        estadoClass += 'status-descartado';
        estadoText = 'NO CUMPLE H1+M15';
    } else if (estadoText.includes('FUERA')) {
        estadoClass += 'status-vigilancia';
        estadoText = 'Fuera Zona';
    } else {
        estadoClass += 'status-descartado';
    }
    
    // Tendencias
    const tendH1 = smc.tendenciaH1 || '--';
    const tendM15 = smc.tendenciaM15 || '--';
    const tendH1Class = getTrendClass(tendH1);
    const tendM15Class = getTrendClass(tendM15);
    
    tr.innerHTML = `
        <td class="index-name">${symbol}</td>
        <td class="${tendH1Class}">${tendH1}</td>
        <td class="${tendM15Class}">${tendM15}</td>
        <td>${lastEventM15}</td>
        <td>${zonaM15HTML}</td>
        <td class="score-cell ${scoreClass}">${score}</td>
        <td class="${ob === 'SÍ' ? 'indicator-yes' : 'indicator-no'}">${ob}</td>
        <td class="${fvg === 'SÍ' ? 'indicator-yes' : 'indicator-no'}">${fvg}</td>
        <td class="${barrida === 'SÍ' ? 'indicator-yes' : 'indicator-no'}">${barrida}</td>
        <td><span class="${estadoClass}">${estadoText}</span></td>
        <td class="price-cell">${formatPrice(data.currentPrice)}</td>
        <td class="time-cell">${formatTime(data.timestamp)}</td>
    `;
    
    return tr;
}

function getTrendClass(trend) {
    if (trend === 'ALCISTA') return 'trend-bull';
    if (trend === 'BAJISTA') return 'trend-bear';
    return 'trend-neutral';
}

// ========================================
// SMC ANALYSIS FUNCTIONS
// ========================================

function direccionOperativaPorIndice(symbol) {
    if (symbol.includes('Boom')) {
        return 'ALCISTA';
    }
    if (symbol.includes('Crash')) {
        return 'BAJISTA';
    }
    return null;
}

function calculateMedian(values) {
    if (values.length === 0) return 0;
    const sorted = values.slice().sort((a, b) => parseFloat(a) - parseFloat(b));
    const mid = Math.floor(sorted.length / 2);
    
    if (sorted.length % 2 === 0) {
        return (parseFloat(sorted[mid - 1]) + parseFloat(sorted[mid])) / 2;
    }
    
    return parseFloat(sorted[mid]);
}

function detectarSwings(candles, lookback = SWING_LOOKBACK) {
    const swings = [];

    for (let i = lookback; i < candles.length - lookback; i++) {
        const high = candles[i].high;
        const low = candles[i].low;

        const prevHighs = candles.slice(i - lookback, i).map(c => c.high);
        const nextHighs = candles.slice(i + 1, i + 1 + lookback).map(c => c.high);

        const prevLows = candles.slice(i - lookback, i).map(c => c.low);
        const nextLows = candles.slice(i + 1, i + 1 + lookback).map(c => c.low);

        if (high > Math.max(...prevHighs) && high > Math.max(...nextHighs)) {
            swings.push({
                index: i,
                timestamp: candles[i].timestamp,
                tipo: 'HIGH',
                precio: parseFloat(high)
            });
        }

        if (low < Math.min(...prevLows) && low < Math.min(...nextLows)) {
            swings.push({
                index: i,
                timestamp: candles[i].timestamp,
                tipo: 'LOW',
                precio: parseFloat(low)
            });
        }
    }

    return swings;
}

function detectarEstructura(candles, swings) {
    const eventos = [];
    let tendencia = null;
    let ultimoHigh = null;
    let ultimoLow = null;
    const nivelesRotos = new Set();

    for (let i = 0; i < candles.length; i++) {
        const close = parseFloat(candles[i].close);
        const high = parseFloat(candles[i].high);
        const low = parseFloat(candles[i].low);
        const timestamp = candles[i].timestamp;

        const swingsPasados = swings.filter(s => s.index < i);

        const highs = swingsPasados.filter(s => s.tipo === 'HIGH');
        const lows = swingsPasados.filter(s => s.tipo === 'LOW');

        if (highs.length > 0) {
            ultimoHigh = highs[highs.length - 1];
        }

        if (lows.length > 0) {
            ultimoLow = lows[lows.length - 1];
        }

        if (!ultimoHigh || !ultimoLow) {
            continue;
        }

        const rompeHigh = CLOSE_BREAK ? close > ultimoHigh.precio : high > ultimoHigh.precio;
        const rompeLow = CLOSE_BREAK ? close < ultimoLow.precio : low < ultimoLow.precio;

        const highKey = `HIGH_${ultimoHigh.index}`;
        const lowKey = `LOW_${ultimoLow.index}`;

        if (rompeHigh && !nivelesRotos.has(highKey)) {
            let evento;
            if (tendencia === null || tendencia === 'ALCISTA') {
                evento = 'BOS_ALCISTA';
                tendencia = 'ALCISTA';
            } else {
                evento = 'CHOCH_ALCISTA';
                tendencia = 'ALCISTA';
            }

            eventos.push({
                timestamp: timestamp,
                index: i,
                evento: evento,
                nivel_roto: ultimoHigh.precio,
                precio_cierre: close
            });

            nivelesRotos.add(highKey);
        } else if (rompeLow && !nivelesRotos.has(lowKey)) {
            let evento;
            if (tendencia === null || tendencia === 'BAJISTA') {
                evento = 'BOS_BAJISTA';
                tendencia = 'BAJISTA';
            } else {
                evento = 'CHOCH_BAJISTA';
                tendencia = 'BAJISTA';
            }

            eventos.push({
                timestamp: timestamp,
                index: i,
                evento: evento,
                nivel_roto: ultimoLow.precio,
                precio_cierre: close
            });

            nivelesRotos.add(lowKey);
        }
    }

    return { eventos, tendencia };
}

function detectarFVG(candles) {
    const fvgs = [];

    for (let i = 2; i < candles.length; i++) {
        const vela1 = candles[i - 2];
        const vela3 = candles[i];

        if (vela3.low > vela1.high) {
            fvgs.push({
                index: i,
                timestamp: candles[i].timestamp,
                tipo: 'FVG_ALCISTA',
                desde: parseFloat(vela1.high),
                hasta: parseFloat(vela3.low)
            });
        }

        if (vela3.high < vela1.low) {
            fvgs.push({
                index: i,
                timestamp: candles[i].timestamp,
                tipo: 'FVG_BAJISTA',
                desde: parseFloat(vela3.high),
                hasta: parseFloat(vela1.low)
            });
        }
    }

    return fvgs;
}

function buscarOrderBlock(candles, evento) {
    const idx = evento.index;
    const direccion = evento.evento.includes('ALCISTA') ? 'ALCISTA' : 'BAJISTA';

    const inicio = Math.max(0, idx - ORDER_BLOCK_LOOKBACK);
    const tramo = candles.slice(inicio, idx);

    if (direccion === 'ALCISTA') {
        const candidatas = tramo.filter(c => c.close < c.open);
        if (candidatas.length === 0) {
            return null;
        }

        const ob = candidatas[candidatas.length - 1];
        return {
            tipo: 'OB_ALCISTA',
            timestamp: ob.timestamp,
            desde: parseFloat(ob.low),
            hasta: parseFloat(ob.high)
        };
    } else {
        const candidatas = tramo.filter(c => c.close > c.open);
        if (candidatas.length === 0) {
            return null;
        }

        const ob = candidatas[candidatas.length - 1];
        return {
            tipo: 'OB_BAJISTA',
            timestamp: ob.timestamp,
            desde: parseFloat(ob.low),
            hasta: parseFloat(ob.high)
        };
    }
}

function detectarBarridaPrevia(candles, evento, direccion, lookback = BARRIDA_LOOKBACK, symbol = null, timeframe = null) {
    const idx = evento.index;
    const inicio = Math.max(0, idx - lookback);
    const tramo = candles.slice(inicio, idx);

    // Debug para Boom 900 Index y M15
    const debugEnabled = symbol === 'Boom 900 Index' && timeframe === 'M15';
    
    if (debugEnabled) {
        console.log('\n' + '='.repeat(80));
        console.log('DEBUG detectarBarridaPrevia (JavaScript)');
        console.log('='.repeat(80));
        console.log(`Evento usado: ${evento.evento || 'N/A'}`);
        console.log(`Index del evento: ${idx}`);
        console.log(`Timestamp del evento: ${evento.timestamp || 'N/A'}`);
        console.log(`Dirección: ${direccion}`);
        console.log(`Lookback usado: ${lookback}`);
        console.log(`Inicio del tramo: ${inicio}`);
        console.log(`Cantidad de velas del tramo: ${tramo.length}`);
        console.log('='.repeat(80));
    }

    if (tramo.length < MIN_SEGMENT_LENGTH) {
        if (debugEnabled) {
            console.log(`RESULTADO: No hay suficientes velas (< ${MIN_SEGMENT_LENGTH})`);
            console.log('='.repeat(80) + '\n');
        }
        return null;
    }

    if (direccion === 'ALCISTA') {
        for (let j = 5; j < tramo.length; j++) {
            const minimoAnterior = Math.min(...tramo.slice(0, j).map(c => c.low));
            const vela = tramo[j];
            
            if (debugEnabled) {
                const condicion = vela.low < minimoAnterior && vela.close > minimoAnterior;
                console.log(`\nj=${j} (índice en tramo):`);
                console.log(`  timestamp: ${vela.timestamp}`);
                console.log(`  low: ${parseFloat(vela.low).toFixed(5)}`);
                console.log(`  high: ${parseFloat(vela.high).toFixed(5)}`);
                console.log(`  close: ${parseFloat(vela.close).toFixed(5)}`);
                console.log(`  minimoAnterior: ${minimoAnterior.toFixed(5)}`);
                console.log(`  Condición: low < minimoAnterior AND close > minimoAnterior`);
                console.log(`  Evaluación: ${parseFloat(vela.low).toFixed(5)} < ${minimoAnterior.toFixed(5)} = ${vela.low < minimoAnterior}`);
                console.log(`              ${parseFloat(vela.close).toFixed(5)} > ${minimoAnterior.toFixed(5)} = ${vela.close > minimoAnterior}`);
                console.log(`  Resultado: ${condicion}`);
            }

            if (vela.low < minimoAnterior && vela.close > minimoAnterior) {
                const resultado = {
                    timestamp: vela.timestamp,
                    tipo: 'BARRIDA_BAJISTA_PREVIA',
                    nivel: minimoAnterior,
                    low: parseFloat(vela.low),
                    close: parseFloat(vela.close)
                };
                if (debugEnabled) {
                    console.log(`\n✓ BARRIDA DETECTADA en j=${j}`);
                    console.log('='.repeat(80) + '\n');
                }
                return resultado;
            }
        }
    } else {
        for (let j = 5; j < tramo.length; j++) {
            const maximoAnterior = Math.max(...tramo.slice(0, j).map(c => c.high));
            const vela = tramo[j];
            
            if (debugEnabled) {
                const condicion = vela.high > maximoAnterior && vela.close < maximoAnterior;
                console.log(`\nj=${j} (índice en tramo):`);
                console.log(`  timestamp: ${vela.timestamp}`);
                console.log(`  low: ${parseFloat(vela.low).toFixed(5)}`);
                console.log(`  high: ${parseFloat(vela.high).toFixed(5)}`);
                console.log(`  close: ${parseFloat(vela.close).toFixed(5)}`);
                console.log(`  maximoAnterior: ${maximoAnterior.toFixed(5)}`);
                console.log(`  Condición: high > maximoAnterior AND close < maximoAnterior`);
                console.log(`  Evaluación: ${parseFloat(vela.high).toFixed(5)} > ${maximoAnterior.toFixed(5)} = ${vela.high > maximoAnterior}`);
                console.log(`              ${parseFloat(vela.close).toFixed(5)} < ${maximoAnterior.toFixed(5)} = ${vela.close < maximoAnterior}`);
                console.log(`  Resultado: ${condicion}`);
            }

            if (vela.high > maximoAnterior && vela.close < maximoAnterior) {
                const resultado = {
                    timestamp: vela.timestamp,
                    tipo: 'BARRIDA_ALCISTA_PREVIA',
                    nivel: maximoAnterior,
                    high: parseFloat(vela.high),
                    close: parseFloat(vela.close)
                };
                if (debugEnabled) {
                    console.log(`\n✓ BARRIDA DETECTADA en j=${j}`);
                    console.log('='.repeat(80) + '\n');
                }
                return resultado;
            }
        }
    }

    if (debugEnabled) {
        console.log('\nRESULTADO: No se detectó barrida');
        console.log('='.repeat(80) + '\n');
    }
    return null;
}

function crearZonaM15(candlesM15, eventosM15, fvgsM15, symbol, precioActual) {
    if (!eventosM15 || eventosM15.length === 0) {
        return null;
    }

    const direccionOperativa = direccionOperativaPorIndice(symbol);
    let eventosFiltrados = eventosM15;

    if (direccionOperativa) {
        eventosFiltrados = eventosM15.filter(e => {
            const direccionEvento = e.evento.includes('ALCISTA') ? 'ALCISTA' : 'BAJISTA';
            return direccionEvento === direccionOperativa;
        });
    }

    if (eventosFiltrados.length === 0) {
        return null;
    }

    for (let i = eventosFiltrados.length - 1; i >= 0; i--) {
        const ultimoEvento = eventosFiltrados[i];
        const direccion = ultimoEvento.evento.includes('ALCISTA') ? 'ALCISTA' : 'BAJISTA';

        const ob = buscarOrderBlock(candlesM15, ultimoEvento);

        const fvgsValidos = fvgsM15.filter(f => {
            const cumpleIndex = f.index <= ultimoEvento.index;
            const cumpleTipo = (direccion === 'ALCISTA' && f.tipo === 'FVG_ALCISTA') ||
                              (direccion === 'BAJISTA' && f.tipo === 'FVG_BAJISTA');
            return cumpleIndex && cumpleTipo;
        });

        const fvg = fvgsValidos.length > 0 ? fvgsValidos[fvgsValidos.length - 1] : null;
        const barrida = detectarBarridaPrevia(candlesM15, ultimoEvento, direccion, BARRIDA_LOOKBACK, symbol, 'M15');

        let zonaDesde = null;
        let zonaHasta = null;

        if (ob && fvg) {
            zonaDesde = Math.min(ob.desde, fvg.desde, fvg.hasta);
            zonaHasta = Math.max(ob.hasta, fvg.desde, fvg.hasta);
        } else if (ob) {
            zonaDesde = ob.desde;
            zonaHasta = ob.hasta;
        } else if (fvg) {
            zonaDesde = Math.min(fvg.desde, fvg.hasta);
            zonaHasta = Math.max(fvg.desde, fvg.hasta);
        }

        if (zonaDesde === null) {
            continue;
        }

        let esUtil = true;
        let motivo = '';

        if (direccionOperativa === 'ALCISTA') {
            esUtil = zonaHasta <= precioActual;
            motivo = esUtil ? 'Zona alcista debajo del precio actual' : 'Zona alcista sobre el precio actual';
        } else if (direccionOperativa === 'BAJISTA') {
            esUtil = zonaDesde >= precioActual;
            motivo = esUtil ? 'Zona bajista sobre el precio actual' : 'Zona bajista debajo del precio actual';
        } else {
            motivo = 'Sin dirección operativa definida';
        }

        let score = 0;
        if (ultimoEvento.evento.includes('CHOCH')) {
            score += 3;
        }
        if (ultimoEvento.evento.includes('BOS')) {
            score += 2;
        }
        if (ob) {
            score += 2;
        }
        if (fvg) {
            score += 2;
        }
        if (barrida) {
            score += 3;
        }
        if (esUtil) {
            score += 2;
        }

        const zona = {
            direccion: direccion,
            evento: ultimoEvento,
            ob: ob,
            fvg: fvg,
            barrida: barrida,
            zona_desde: zonaDesde,
            zona_hasta: zonaHasta,
            score: score,
            es_util: esUtil,
            motivo: motivo,
            direccion_operativa: direccionOperativa,
            debug_evento_usado_index: ultimoEvento.index,
            debug_evento_usado_timestamp: ultimoEvento.timestamp
        };

        if (esUtil) {
            return zona;
        }
    }

    return null;
}

function crearZonaFinaM1(candlesM1, zonaM15, symbol) {
    if (!candlesM1 || candlesM1.length === 0 || !zonaM15) {
        return null;
    }

    const precioActual = parseFloat(candlesM1[candlesM1.length - 1].close);
    const direccionOperativa = direccionOperativaPorIndice(symbol);

    const indicesCercanos = [];
    for (let i = 0; i < candlesM1.length; i++) {
        const c = candlesM1[i];
        if (c.high >= zonaM15.zona_desde && c.low <= zonaM15.zona_hasta) {
            indicesCercanos.push(i);
        }
    }

    let tramo;
    let confirmacion;

    if (indicesCercanos.length > 0) {
        const idx = indicesCercanos[indicesCercanos.length - 1];
        const inicio = Math.max(0, idx - M1_VELAS_ZONA + 1);
        tramo = candlesM1.slice(inicio, idx + 1);
        confirmacion = 'M1 dentro/cerca de zona madre M15';
    } else {
        tramo = candlesM1.slice(-M1_VELAS_ZONA);
        confirmacion = 'M1 últimas velas cercanas al precio actual';
    }

    if (tramo.length === 0) {
        return null;
    }

    let zonaDesde, zonaHasta;

    if (direccionOperativa === 'ALCISTA') {
        zonaDesde = Math.min(...tramo.map(c => c.low));
        zonaHasta = calculateMedian(tramo.map(c => c.close));
    } else if (direccionOperativa === 'BAJISTA') {
        zonaDesde = calculateMedian(tramo.map(c => c.close));
        zonaHasta = Math.max(...tramo.map(c => c.high));
    } else {
        zonaDesde = Math.min(...tramo.map(c => c.low));
        zonaHasta = Math.max(...tramo.map(c => c.high));
    }

    if (zonaDesde > zonaHasta) {
        [zonaDesde, zonaHasta] = [zonaHasta, zonaDesde];
    }

    const precioDentroM1 = precioActual >= zonaDesde && precioActual <= zonaHasta;

    return {
        zona_m1_desde: zonaDesde,
        zona_m1_hasta: zonaHasta,
        m1_confirmacion: confirmacion,
        velas_m1_usadas: M1_VELAS_ZONA,
        precio_dentro_m1: precioDentroM1
    };
}

function analyzeSMC(candlesH1, candlesM15, candlesM1, symbol) {
    let swingsH1 = [];
    let eventosH1 = [];
    let tendenciaH1 = null;
    
    if (candlesH1 && candlesH1.length > 0) {
        swingsH1 = detectarSwings(candlesH1);
        const resultH1 = detectarEstructura(candlesH1, swingsH1);
        eventosH1 = resultH1.eventos;
        tendenciaH1 = resultH1.tendencia;
    }

    const swingsM15 = detectarSwings(candlesM15);
    const { eventos: eventosM15, tendencia: tendenciaM15 } = detectarEstructura(candlesM15, swingsM15);

    const fvgsM15 = detectarFVG(candlesM15);

    const precioActual = candlesM15.length > 0 ? parseFloat(candlesM15[candlesM15.length - 1].close) : null;

    const zonaM15 = crearZonaM15(candlesM15, eventosM15, fvgsM15, symbol, precioActual);

    const zonaM1 = candlesM1 && candlesM1.length > 0 ? crearZonaFinaM1(candlesM1, zonaM15, symbol) : null;

    let estado = '--';
    if (zonaM15 && precioActual !== null) {
        if (precioActual >= zonaM15.zona_desde && precioActual <= zonaM15.zona_hasta) {
            estado = 'PRECIO_DENTRO_DE_ZONA';
        } else {
            estado = 'PRECIO_FUERA_DE_ZONA';
        }
    }

    return {
        tendenciaH1: tendenciaH1 || '--',
        tendenciaM15: tendenciaM15 || '--',
        eventosH1: eventosH1,
        eventosM15: eventosM15,
        zonaM15: zonaM15,
        zonaM1: zonaM1,
        precioActual: precioActual,
        estado: estado,
        direccionOperativa: direccionOperativaPorIndice(symbol)
    };
}

// ========================================
// UTILITY FUNCTIONS
// ========================================

function formatPrice(price) {
    if (price === null || price === undefined) return '--';
    return parseFloat(price).toFixed(5);
}

function formatTime(timestamp) {
    if (!timestamp) return '--';
    
    try {
        const date = new Date(timestamp);
        return date.toLocaleTimeString('es-ES', {
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch (error) {
        return '--';
    }
}

function updateLastUpdateTime() {
    const now = new Date();
    const timeString = now.toLocaleTimeString('es-ES', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
    const elem = document.getElementById('lastUpdate');
    if (elem) {
        elem.textContent = `Última actualización: ${timeString}`;
    }
}

// ========================================
// COPY TO CLIPBOARD
// ========================================

function copyToClipboard(value, button) {
    // Get just the numeric value without formatting
    const numericValue = parseFloat(value).toString();
    
    // Copy to clipboard
    navigator.clipboard.writeText(numericValue).then(() => {
        // Visual feedback
        const originalHTML = button.innerHTML;
        button.innerHTML = '✓';
        button.classList.add('copied');
        
        setTimeout(() => {
            button.innerHTML = originalHTML;
            button.classList.remove('copied');
        }, 1500);
    }).catch(err => {
        console.error('Error copying to clipboard:', err);
        alert('Error al copiar');
    });
}

// ========================================
// HISTORY TABLE FUNCTIONS
// ========================================

// Global variables for filtering
let allSetups = [];
let currentFilters = {
    symbol: 'todos',
    estado: 'todos'
};

async function fetchSetupHistory(limit = 50) {
    // Lee desde la tabla correspondiente a la estrategia seleccionada en historial
    const table = getStrategyTable(currentHistoryStrategy);
    const url = `${SUPABASE_URL}/rest/v1/${table}?order=created_at.desc&limit=${limit}`;
    
    const response = await fetch(url, {
        method: 'GET',
        headers: {
            'apikey': SUPABASE_ANON_KEY,
            'Authorization': `Bearer ${SUPABASE_ANON_KEY}`,
            'Content-Type': 'application/json'
        }
    });
    
    if (!response.ok) {
        throw new Error(`Error HTTP: ${response.status}`);
    }
    
    return await response.json();
}

function initializeHistoryFilters() {
    // Symbol filters
    const symbolFilters = document.querySelectorAll('#symbolFilters .filter-btn');
    symbolFilters.forEach(btn => {
        btn.addEventListener('click', () => {
            // Remove active from all
            symbolFilters.forEach(b => b.classList.remove('active'));
            // Add active to clicked
            btn.classList.add('active');
            // Update filter
            currentFilters.symbol = btn.getAttribute('data-filter');
            // Apply filters
            applyFilters();
        });
    });
    
    // Estado filters
    const estadoFilters = document.querySelectorAll('#estadoFilters .filter-btn');
    estadoFilters.forEach(btn => {
        btn.addEventListener('click', () => {
            estadoFilters.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentFilters.estado = btn.getAttribute('data-filter');
            applyFilters();
        });
    });
}

/**
 * Calculate statistics from filtered setups
 * @param {Array} setups - Array of setup objects
 * @returns {Object} Stats object with counts for each state
 */
function calculateStats(setups) {
    const stats = {
        total: setups.length,
        activas: 0,
        enZona: 0,
        profit: 0,
        tp: 0,
        sl: 0,
        descartadas: 0
    };
    
    setups.forEach(setup => {
        switch (setup.estado) {
            case 'ACTIVA':
                stats.activas++;
                break;
            case 'EN_ZONA':
                stats.enZona++;
                break;
            case 'PROFIT':
                stats.profit++;
                break;
            case 'TP':
                stats.tp++;
                break;
            case 'SL':
                stats.sl++;
                break;
            case 'DESCARTADA':
                stats.descartadas++;
                break;
            default:
                // Handle unexpected state values
                console.warn(`Unexpected estado value: ${setup.estado} for setup ID ${setup.id}`);
                break;
        }
    });
    
    return stats;
}

/**
 * Calculate statistics per index from filtered setups
 * @param {Array} setups - Array of setup objects
 * @returns {Object} Stats per symbol
 */
function calculateIndexStats(setups) {
    const indexStats = {};
    
    setups.forEach(setup => {
        const symbol = setup.symbol;
        
        if (!indexStats[symbol]) {
            indexStats[symbol] = {
                total: 0,
                tp: 0,
                sl: 0,
                activas: 0,
                enZona: 0,
                profit: 0,
                descartadas: 0
            };
        }
        
        indexStats[symbol].total++;
        
        switch (setup.estado) {
            case 'TP':
                indexStats[symbol].tp++;
                break;
            case 'SL':
                indexStats[symbol].sl++;
                break;
            case 'ACTIVA':
                indexStats[symbol].activas++;
                break;
            case 'EN_ZONA':
                indexStats[symbol].enZona++;
                break;
            case 'PROFIT':
                indexStats[symbol].profit++;
                break;
            case 'DESCARTADA':
                indexStats[symbol].descartadas++;
                break;
        }
    });
    
    return {
        indexStats
    };
}

/**
 * Render statistics cards in the stats bar with per-index TP/SL counts
 * @param {Object} stats - Stats object from calculateStats
 * @param {Array} setups - Array of all filtered setups
 */
function renderStats(stats, setups = []) {
    const statsBar = document.getElementById('stats-bar');
    if (!statsBar) return;
    
    // Calculate winrate
    const totalClosed = stats.tp + stats.sl;
    const winrate = totalClosed > 0 ? ((stats.tp / totalClosed) * 100).toFixed(1) : '0.0';
    
    // Calculate index statistics
    const { indexStats } = calculateIndexStats(setups);
    
    // Create per-index TP/SL counters HTML (dynamic and scalable)
    let perIndexHTML = '';
    if (Object.keys(indexStats).length > 0) {
        // Sort symbols alphabetically for consistent display
        const sortedSymbols = Object.keys(indexStats).sort();
        
        // Create SL row
        const slRow = sortedSymbols.map(symbol => {
            const shortName = symbol.replace(' Index', '');
            const slCount = indexStats[symbol].sl;
            return `<div class="stat-index-box stat-index-sl-box">${shortName} | ${slCount}</div>`;
        }).join('');
        
        // Create TP row
        const tpRow = sortedSymbols.map(symbol => {
            const shortName = symbol.replace(' Index', '');
            const tpCount = indexStats[symbol].tp;
            return `<div class="stat-index-box stat-index-tp-box">${shortName} | ${tpCount}</div>`;
        }).join('');
        
        perIndexHTML = `
            <div class="stat-per-index-container">
                <div class="stat-per-index-row">
                    <div class="stat-per-index-label">SL →</div>
                    <div class="stat-per-index-boxes">${slRow}</div>
                </div>
                <div class="stat-per-index-row">
                    <div class="stat-per-index-label">TP →</div>
                    <div class="stat-per-index-boxes">${tpRow}</div>
                </div>
            </div>
        `;
    }
    
    // Create stats cards
    statsBar.innerHTML = `
        <div class="stat-card stat-total">
            <div class="stat-label">Total Setups</div>
            <div class="stat-value">${stats.total}</div>
        </div>
        <div class="stat-card stat-activas">
            <div class="stat-label">Activas</div>
            <div class="stat-value">${stats.activas}</div>
        </div>
        <div class="stat-card stat-en-zona">
            <div class="stat-label">En Zona</div>
            <div class="stat-value">${stats.enZona}</div>
        </div>
        <div class="stat-card stat-profit">
            <div class="stat-label">Profit</div>
            <div class="stat-value">${stats.profit}</div>
        </div>
        <div class="stat-card stat-tp">
            <div class="stat-label">TP</div>
            <div class="stat-value">${stats.tp}</div>
        </div>
        <div class="stat-card stat-sl">
            <div class="stat-label">SL</div>
            <div class="stat-value">${stats.sl}</div>
        </div>
        <div class="stat-card stat-descartadas">
            <div class="stat-label">Descartadas</div>
            <div class="stat-value">${stats.descartadas}</div>
        </div>
        <div class="stat-card stat-winrate">
            <div class="stat-label">Winrate</div>
            <div class="stat-value">${winrate}%</div>
        </div>
        ${perIndexHTML}
    `;
}

function applyFilters() {
    const tbody = document.getElementById('historyTableBody');
    if (!tbody) return;
    
    // Filter setups
    let filteredSetups = allSetups.filter(setup => {
        // Symbol filter
        if (currentFilters.symbol !== 'todos' && setup.symbol !== currentFilters.symbol) {
            return false;
        }
        
        // Estado filter
        if (currentFilters.estado !== 'todos' && setup.estado !== currentFilters.estado) {
            return false;
        }
        
        return true;
    });
    
    // Calculate and render stats for filtered data
    const stats = calculateStats(filteredSetups);
    renderStats(stats, filteredSetups);
    
    // Update table
    tbody.innerHTML = '';
    
    if (filteredSetups.length === 0) {
        tbody.innerHTML = '<tr><td colspan="15" class="loading">No hay datos con los filtros seleccionados</td></tr>';
        return;
    }
    
    filteredSetups.forEach(setup => {
        const row = createHistoryRow(setup);
        tbody.appendChild(row);
    });
}

async function updateHistoryTable() {
    const historyError = document.getElementById('historyError');
    const tbody = document.getElementById('historyTableBody');
    
    if (!tbody) return; // Table not in DOM yet
    
    // Update history last update time
    const historyLastUpdate = document.getElementById('historyLastUpdate');
    if (historyLastUpdate) {
        const now = new Date();
        const timeString = now.toLocaleTimeString('es-ES', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
        historyLastUpdate.textContent = `Última actualización: ${timeString}`;
    }
    
    try {
        // Hide error message
        if (historyError) {
            historyError.style.display = 'none';
        }
        
        tbody.innerHTML = '<tr><td colspan="15" class="loading">Cargando historial...</td></tr>';
        
        const setups = await fetchSetupHistory();
        
        // Store all setups globally
        allSetups = setups;
        
        // Initialize filters if not already done
        if (!document.querySelector('#symbolFilters .filter-btn[data-filter="todos"]').dataset.initialized) {
            initializeHistoryFilters();
            document.querySelector('#symbolFilters .filter-btn[data-filter="todos"]').dataset.initialized = 'true';
        }
        
        // Reset filters to default
        currentFilters = {
            symbol: 'todos',
            estado: 'todos'
        };
        
        // Reset active states
        document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
        document.querySelector('#symbolFilters .filter-btn[data-filter="todos"]').classList.add('active');
        document.querySelector('#estadoFilters .filter-btn[data-filter="todos"]').classList.add('active');
        
        // Apply filters (which will show all since filters are 'todos')
        applyFilters();
        
    } catch (error) {
        console.error('Error updating history table:', error);
        
        // Show clear error message
        if (historyError) {
            if (error.message.includes('401') || error.message.includes('403')) {
                historyError.textContent = `⚠️ No se pudo cargar historial. Revisar permisos RLS de ${getStrategyTable(currentHistoryStrategy)}.`;
            } else {
                historyError.textContent = `⚠️ Error cargando historial: ${error.message}`;
            }
            historyError.style.display = 'block';
        }
        
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="15" class="loading">Error cargando historial</td></tr>';
        }
    }
}

function createHistoryRow(setup) {
    const tr = document.createElement('tr');
    
    // Format date
    const fecha = setup.created_at ? new Date(setup.created_at).toLocaleString('es-ES', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    }) : '--';
    
    // Zone text
    const zonaText = `${formatPrice(setup.zona_desde)} - ${formatPrice(setup.zona_hasta)}`;
    
    // TP and SL prices
    const tpText = setup.tp_price != null ? formatPrice(setup.tp_price) : '--';
    const slText = setup.sl_price != null ? formatPrice(setup.sl_price) : '--';
    
    // Tendencias
    const tendH1 = setup.tendencia_h1 || '--';
    const tendM15 = setup.tendencia_m15 || '--';
    const tendH1Class = getTrendClass(tendH1);
    const tendM15Class = getTrendClass(tendM15);
    
    // Último evento M15 - read from evento column
    const ultimoEventoM15 = setup.evento || '--';
    
    // Score class
    let scoreClass = 'score-low';
    if (setup.score >= 8) scoreClass = 'score-high';
    else if (setup.score >= 5) scoreClass = 'score-medium';
    
    // Estado class
    let estadoClass = 'status-badge ';
    let estadoText = setup.estado || '--';
    
    switch (setup.estado) {
        case 'ACTIVA':
            estadoClass += 'status-activa';
            break;
        case 'EN_ZONA':
            estadoClass += 'status-esperando';
            estadoText = 'EN ZONA';
            break;
        case 'PROFIT':
            estadoClass += 'status-profit';
            break;
        case 'PAUSADA':
            estadoClass += 'status-pausada';
            break;
        case 'DESCARTADA':
            estadoClass += 'status-descartada';
            break;
        case 'TP':
            estadoClass += 'status-tp';
            break;
        case 'SL':
            estadoClass += 'status-sl';
            break;
        default:
            estadoClass += 'status-descartado';
    }
    
    // OB, FVG, Barrida
    const obText = setup.ob ? 'SÍ' : 'NO';
    const fvgText = setup.fvg ? 'SÍ' : 'NO';
    const barridaText = setup.barrida ? 'SÍ' : 'NO';
    
    // Resultado puntos
    const resultadoPuntos = setup.resultado_puntos != null ? formatPrice(setup.resultado_puntos) : '--';
    
    // Max reaccion - show "--" if estado is ACTIVA or PAUSADA, only show value for EN_ZONA, PROFIT and other states
    let maxReaccion = '--';
    if (setup.estado === 'ACTIVA' || setup.estado === 'PAUSADA') {
        // For ACTIVA and PAUSADA setups, always show "--"
        maxReaccion = '--';
    } else if (setup.estado === 'EN_ZONA' || setup.estado === 'PROFIT') {
        // For EN_ZONA and PROFIT setups, calculate and show max_reaccion_puntos
        maxReaccion = setup.max_reaccion_puntos != null ? formatPrice(setup.max_reaccion_puntos) : '--';
    } else {
        // For other states (TP, SL, DESCARTADA), show the value if available
        maxReaccion = setup.max_reaccion_puntos != null ? formatPrice(setup.max_reaccion_puntos) : '--';
    }
    
    tr.innerHTML = `
        <td class="time-cell">${fecha}</td>
        <td>${setup.symbol || '--'}</td>
        <td class="${tendH1Class}">${tendH1}</td>
        <td class="${tendM15Class}">${tendM15}</td>
        <td>${ultimoEventoM15}</td>
        <td class="zone-cell">${zonaText}</td>
        <td class="price-cell">${tpText}</td>
        <td class="price-cell">${slText}</td>
        <td class="score-cell ${scoreClass}">${setup.score || 0}</td>
        <td class="${setup.ob ? 'indicator-yes' : 'indicator-no'}">${obText}</td>
        <td class="${setup.fvg ? 'indicator-yes' : 'indicator-no'}">${fvgText}</td>
        <td class="${setup.barrida ? 'indicator-yes' : 'indicator-no'}">${barridaText}</td>
        <td><span class="${estadoClass}">${estadoText}</span></td>
        <td class="price-cell">${resultadoPuntos}</td>
        <td class="price-cell">${maxReaccion}</td>
    `;
    
    return tr;
}

// Cleanup
window.addEventListener('beforeunload', () => {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
    }
});
