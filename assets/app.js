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

function startAutoRefresh() {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
    }
    
    autoRefreshInterval = setInterval(() => {
        fetchAllIndices();
    }, AUTO_REFRESH_SECONDS * 1000);
}

// ========================================
// SMC M15 SETUPS TRACKING
// ========================================

async function getActiveSetup(symbol) {
    const url = `${SUPABASE_URL}/rest/v1/smc_m15_setups?symbol=eq.${encodeURIComponent(symbol)}&estado=eq.ACTIVA&order=created_at.desc&limit=1`;
    
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
    return data.length > 0 ? data[0] : null;
}

async function createSetup(setupData) {
    const url = `${SUPABASE_URL}/rest/v1/smc_m15_setups`;
    
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

async function updateSetup(id, updateData) {
    const url = `${SUPABASE_URL}/rest/v1/smc_m15_setups?id=eq.${id}`;
    
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

async function closeSetup(id, motivo) {
    return await updateSetup(id, {
        estado: 'DESCARTADA',
        fecha_cierre: new Date().toISOString(),
        motivo_cierre: motivo
    });
}

function zonesAreEqual(zone1, zone2) {
    if (!zone1 || !zone2) return false;
    
    // Compare zones with a small tolerance (0.00001 for precision)
    const tolerance = 0.00001;
    return Math.abs(zone1.zona_desde - zone2.zona_desde) < tolerance &&
           Math.abs(zone1.zona_hasta - zone2.zona_hasta) < tolerance &&
           zone1.direccion === zone2.direccion;
}

async function trackZoneHistory(symbol, analysis) {
    try {
        const zonaM15 = analysis.smc.zonaM15;
        const currentPrice = analysis.currentPrice;
        
        if (!zonaM15 || !zonaM15.es_util) {
            return; // Only track useful zones
        }
        
        // Get tipo_indice (Boom or Crash)
        const tipoIndice = symbol.includes('Boom') ? 'Boom' : 'Crash';
        
        // Check for active setup
        const activeSetup = await getActiveSetup(symbol);
        
        if (!activeSetup) {
            // No active setup, create new one
            const newSetup = {
                symbol: symbol,
                tipo_indice: tipoIndice,
                direccion: zonaM15.direccion,
                zona_desde: zonaM15.zona_desde,
                zona_hasta: zonaM15.zona_hasta,
                zona_size_puntos: Math.abs(zonaM15.zona_hasta - zonaM15.zona_desde),
                precio_actual_detectado: currentPrice,
                precio_entrada_referencia: zonaM15.direccion === 'ALCISTA' ? zonaM15.zona_hasta : zonaM15.zona_desde,
                score: zonaM15.score,
                evento: zonaM15.evento ? zonaM15.evento.evento : null,
                ob: zonaM15.ob ? true : false,
                fvg: zonaM15.fvg ? true : false,
                barrida: zonaM15.barrida ? true : false,
                estado: 'ACTIVA',
                tp_price: null,
                sl_price: null,
                ratio_rr: null,
                max_reaccion_puntos: 0,
                resultado_puntos: null,
                fecha_cierre: null,
                motivo_cierre: null
            };
            
            await createSetup(newSetup);
            console.log(`✓ Nuevo setup ACTIVO creado para ${symbol}`);
            
        } else {
            // Active setup exists
            const activeZone = {
                zona_desde: activeSetup.zona_desde,
                zona_hasta: activeSetup.zona_hasta,
                direccion: activeSetup.direccion
            };
            
            if (zonesAreEqual(activeZone, zonaM15)) {
                // Same zone, update updated_at and max_reaccion_puntos
                const distanceFromZone = zonaM15.direccion === 'ALCISTA' 
                    ? Math.max(0, currentPrice - zonaM15.zona_hasta)
                    : Math.max(0, zonaM15.zona_desde - currentPrice);
                
                const newMaxReaccion = Math.max(activeSetup.max_reaccion_puntos || 0, distanceFromZone);
                
                await updateSetup(activeSetup.id, {
                    updated_at: new Date().toISOString(),
                    max_reaccion_puntos: newMaxReaccion,
                    score: zonaM15.score // Update score in case it changed
                });
                
                console.log(`✓ Setup actualizado para ${symbol} - max_reaccion: ${newMaxReaccion.toFixed(5)}`);
                
            } else {
                // Different zone detected, close previous and create new
                await closeSetup(activeSetup.id, 'Nueva zona detectada');
                console.log(`✓ Setup anterior cerrado para ${symbol} - Nueva zona detectada`);
                
                // Create new setup
                const newSetup = {
                    symbol: symbol,
                    tipo_indice: tipoIndice,
                    direccion: zonaM15.direccion,
                    zona_desde: zonaM15.zona_desde,
                    zona_hasta: zonaM15.zona_hasta,
                    zona_size_puntos: Math.abs(zonaM15.zona_hasta - zonaM15.zona_desde),
                    precio_actual_detectado: currentPrice,
                    precio_entrada_referencia: zonaM15.direccion === 'ALCISTA' ? zonaM15.zona_hasta : zonaM15.zona_desde,
                    score: zonaM15.score,
                    evento: zonaM15.evento ? zonaM15.evento.evento : null,
                    ob: zonaM15.ob ? true : false,
                    fvg: zonaM15.fvg ? true : false,
                    barrida: zonaM15.barrida ? true : false,
                    estado: 'ACTIVA',
                    tp_price: null,
                    sl_price: null,
                    ratio_rr: null,
                    max_reaccion_puntos: 0,
                    resultado_puntos: null,
                    fecha_cierre: null,
                    motivo_cierre: null
                };
                
                await createSetup(newSetup);
                console.log(`✓ Nuevo setup ACTIVO creado para ${symbol}`);
            }
        }
        
    } catch (error) {
        console.error(`Error tracking zone history for ${symbol}:`, error);
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
            
            // Track zone history for SMC M15 PRO
            if (analysis && !analysis.error && analysis.smc && analysis.smc.zonaM15) {
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
    updateBoomTable(results);
    updateCrashTable(results);
    
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

function updateBoomTable(results) {
    const tbody = document.getElementById('boomTableBody');
    tbody.innerHTML = '';
    
    ALL_INDICES.boom.forEach(symbol => {
        const row = createTableRow(symbol, results[symbol]);
        tbody.appendChild(row);
    });
}

function updateCrashTable(results) {
    const tbody = document.getElementById('crashTableBody');
    tbody.innerHTML = '';
    
    ALL_INDICES.crash.forEach(symbol => {
        const row = createTableRow(symbol, results[symbol]);
        tbody.appendChild(row);
    });
}

function createTableRow(symbol, data) {
    const tr = document.createElement('tr');
    
    if (!data || data.error) {
        tr.innerHTML = `
            <td class="index-name">${symbol}</td>
            <td colspan="13" class="loading">${data ? data.message : 'Cargando...'}</td>
        `;
        return tr;
    }
    
    const smc = data.smc;
    
    // Get last event M15
    let lastEventM15 = '--';
    if (smc.eventosM15 && smc.eventosM15.length > 0) {
        const evento = smc.eventosM15[smc.eventosM15.length - 1];
        lastEventM15 = `${evento.evento}`;
    }
    
    // Zone M15 with individual boxes
    let zonaM15HTML = '<span class="zone-cell">--</span>';
    if (smc.zonaM15) {
        zonaM15HTML = `
            <div class="zone-boxes">
                <div class="zone-price-row">
                    <span class="zone-label">Desde:</span>
                    <span class="zone-price">${formatPrice(smc.zonaM15.zona_desde)}</span>
                    <button class="copy-btn" onclick="copyToClipboard('${smc.zonaM15.zona_desde}', this)">📋</button>
                </div>
                <div class="zone-price-row">
                    <span class="zone-label">Hasta:</span>
                    <span class="zone-price">${formatPrice(smc.zonaM15.zona_hasta)}</span>
                    <button class="copy-btn" onclick="copyToClipboard('${smc.zonaM15.zona_hasta}', this)">📋</button>
                </div>
            </div>
        `;
    }
    
    // Zone M1 with individual boxes
    let zonaM1HTML = '<span class="zone-cell">--</span>';
    if (smc.zonaM1) {
        zonaM1HTML = `
            <div class="zone-boxes">
                <div class="zone-price-row">
                    <span class="zone-label">Desde:</span>
                    <span class="zone-price">${formatPrice(smc.zonaM1.zona_m1_desde)}</span>
                    <button class="copy-btn" onclick="copyToClipboard('${smc.zonaM1.zona_m1_desde}', this)">📋</button>
                </div>
                <div class="zone-price-row">
                    <span class="zone-label">Hasta:</span>
                    <span class="zone-price">${formatPrice(smc.zonaM1.zona_m1_hasta)}</span>
                    <button class="copy-btn" onclick="copyToClipboard('${smc.zonaM1.zona_m1_hasta}', this)">📋</button>
                </div>
            </div>
        `;
    }
    
    // Score
    const score = smc.zonaM15 ? smc.zonaM15.score : 0;
    let scoreClass = 'score-low';
    if (score >= 8) scoreClass = 'score-high';
    else if (score >= 5) scoreClass = 'score-medium';
    
    // OB, FVG, Barrida
    const ob = smc.zonaM15 && smc.zonaM15.ob ? 'SÍ' : 'NO';
    const fvg = smc.zonaM15 && smc.zonaM15.fvg ? 'SÍ' : 'NO';
    const barrida = smc.zonaM15 && smc.zonaM15.barrida ? 'SÍ' : 'NO';
    
    // Estado
    let estadoText = smc.estado || '--';
    let estadoClass = 'status-badge ';
    if (estadoText.includes('DENTRO')) {
        estadoClass += 'status-esperando';
        estadoText = 'En Zona';
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
    
    // Dirección
    const direccion = smc.direccionOperativa || '--';
    const direccionClass = direccion === 'ALCISTA' ? 'direction-alcista' : 'direction-bajista';
    
    tr.innerHTML = `
        <td class="index-name">${symbol}</td>
        <td class="${tendH1Class}">${tendH1}</td>
        <td class="${tendM15Class}">${tendM15}</td>
        <td class="direction-cell ${direccionClass}">${direccion}</td>
        <td>${lastEventM15}</td>
        <td>${zonaM15HTML}</td>
        <td>${zonaM1HTML}</td>
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
    estado: 'todos',
    direccion: 'todos'
};

async function fetchSetupHistory(limit = 50) {
    const url = `${SUPABASE_URL}/rest/v1/smc_m15_setups?order=created_at.desc&limit=${limit}`;
    
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
    
    // Direccion filters
    const direccionFilters = document.querySelectorAll('#direccionFilters .filter-btn');
    direccionFilters.forEach(btn => {
        btn.addEventListener('click', () => {
            direccionFilters.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentFilters.direccion = btn.getAttribute('data-filter');
            applyFilters();
        });
    });
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
        
        // Direccion filter
        if (currentFilters.direccion !== 'todos' && setup.direccion !== currentFilters.direccion) {
            return false;
        }
        
        return true;
    });
    
    // Update table
    tbody.innerHTML = '';
    
    if (filteredSetups.length === 0) {
        tbody.innerHTML = '<tr><td colspan="11" class="loading">No hay datos con los filtros seleccionados</td></tr>';
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
        
        tbody.innerHTML = '<tr><td colspan="11" class="loading">Cargando historial...</td></tr>';
        
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
            estado: 'todos',
            direccion: 'todos'
        };
        
        // Reset active states
        document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
        document.querySelector('#symbolFilters .filter-btn[data-filter="todos"]').classList.add('active');
        document.querySelector('#estadoFilters .filter-btn[data-filter="todos"]').classList.add('active');
        document.querySelector('#direccionFilters .filter-btn[data-filter="todos"]').classList.add('active');
        
        // Apply filters (which will show all since filters are 'todos')
        applyFilters();
        
    } catch (error) {
        console.error('Error updating history table:', error);
        
        // Show clear error message
        if (historyError) {
            if (error.message.includes('401') || error.message.includes('403')) {
                historyError.textContent = '⚠️ No se pudo cargar historial. Revisar permisos RLS de smc_m15_setups.';
            } else {
                historyError.textContent = `⚠️ Error cargando historial: ${error.message}`;
            }
            historyError.style.display = 'block';
        }
        
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="11" class="loading">Error cargando historial</td></tr>';
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
    
    // Direction class
    const direccionClass = setup.direccion === 'ALCISTA' ? 'direction-alcista' : 'direction-bajista';
    
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
    
    // Max reaccion - show "--" if setup is ACTIVA and not touched/evaluated
    let maxReaccion = '--';
    if (setup.estado === 'ACTIVA') {
        // For active setups, only show value if it's been touched (max_reaccion_puntos > 0)
        if (setup.max_reaccion_puntos != null && setup.max_reaccion_puntos > 0) {
            maxReaccion = formatPrice(setup.max_reaccion_puntos);
        } else {
            maxReaccion = '--';
        }
    } else {
        // For non-active setups, show the value if available
        maxReaccion = setup.max_reaccion_puntos != null ? formatPrice(setup.max_reaccion_puntos) : '--';
    }
    
    tr.innerHTML = `
        <td class="time-cell">${fecha}</td>
        <td>${setup.symbol || '--'}</td>
        <td class="direction-cell ${direccionClass}">${setup.direccion || '--'}</td>
        <td class="zone-cell">${zonaText}</td>
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
