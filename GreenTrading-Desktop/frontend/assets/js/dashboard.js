console.log("DASHBOARD_JS_VERSION: FIX_DASHBOARD_STABILITY_V2");

/**
 * GreenTrading Desktop - Dashboard JavaScript
 * Phase 3: SMC M15 PRO dashboard with real-time SMC analysis
 */

// Auto-refresh interval (1 second)
const AUTO_REFRESH_INTERVAL = 1000;
let refreshIntervalId = null;

// Concurrency guard: skip refresh if a fetch is already in progress
let isFetchingSnapshot = false;

/**
 * Initialize dashboard
 */
async function initDashboard() {
    console.log('🚀 Initializing GreenTrading Desktop Dashboard...');
    
    // Setup event listeners
    setupEventListeners();
    
    // Initial data load
    await loadDashboardData();
    
    // Start auto-refresh
    startAutoRefresh();
    
    console.log('✅ Dashboard initialized');
}

/**
 * Setup event listeners
 */
function setupEventListeners() {
    // Refresh button
    const refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', async () => {
            console.log('Manual refresh triggered');
            await loadDashboardData();
        });
    }
}

/**
 * Load dashboard data from backend
 */
async function loadDashboardData() {
    if (isFetchingSnapshot) {
        console.log('SNAPSHOT FETCH SKIPPED_ALREADY_RUNNING');
        return;
    }

    isFetchingSnapshot = true;
    console.log('SNAPSHOT FETCH START');
    
    try {
        // Call SMC API through exposed window.api
        const result = await window.api.getSmcM15ProSnapshot();
        
        console.log("DEBUG RESULT FULL:", result);
        console.log("DEBUG RESULT.DATA:", result.data);
        console.log("DEBUG FIRST ITEM:", result.data?.[0]);
        
        if (!result.success) {
            throw new Error(result.error || 'Failed to load SMC data');
        }
        
        const snapshots = result.data;
        
        console.log("DEBUG SNAPSHOTS IS ARRAY:", Array.isArray(snapshots));
        console.log("DEBUG SNAPSHOTS FIRST:", snapshots?.[0]);
        console.log(`SNAPSHOT FETCH OK - ${snapshots.length} snapshots`);
        
        // Update connection status
        updateConnectionStatus(true);
        
        // Separate into Boom and Crash
        const boomData = snapshots.filter(s => s.symbol.includes('Boom'));
        const crashData = snapshots.filter(s => s.symbol.includes('Crash'));
        
        // Render tables
        renderTable('boomTableBody', boomData);
        renderTable('crashTableBody', crashData);
        
        // Update timestamp
        updateLastUpdateTime();
        
    } catch (error) {
        console.error('SNAPSHOT FETCH ERROR:', error.message);
        updateConnectionStatus(false);
        showError(error.message);
    } finally {
        isFetchingSnapshot = false;
    }
}

/**
 * Render table with symbol data
 */
function renderTable(tableBodyId, data) {
    const tbody = document.getElementById(tableBodyId);
    if (!tbody) {
        console.error(`Table body ${tableBodyId} not found`);
        return;
    }
    
    if (data.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="12" class="loading-cell" style="text-align: center; padding: 20px;">
                    No hay datos disponibles
                </td>
            </tr>
        `;
        return;
    }
    
    // Generate rows
    const rows = data.map(snapshot => createTableRow(snapshot)).join('');
    tbody.innerHTML = rows;
}

/**
 * Create table row for a symbol snapshot (SMC M15 PRO)
 */
function createTableRow(snapshot) {
    console.log("DEBUG ROW SNAPSHOT:", snapshot);
    console.log("DEBUG ROW H1:", snapshot?.tendencia_h1);
    console.log("DEBUG ROW M15:", snapshot?.tendencia_m15);
    console.log("DEBUG ROW EVENT:", snapshot?.ultimo_evento_m15);
    console.log("DEBUG ROW ZONE:", snapshot?.zona_madre_m15);
    console.log("DEBUG ROW SCORE:", snapshot?.score);
    console.log("DEBUG ROW ESTADO:", snapshot?.estado);
    console.log("DEBUG ROW ESTADO_FINAL:", snapshot?.estado_final);
    console.log("DEBUG ROW ESTADO_HISTORIAL:", snapshot?.estado_historial);
    
    const {
        symbol,
        price,
        tendencia_h1,
        tendencia_m15,
        ultimo_evento_m15,
        zona_madre_m15,
        entrada,
        stoploss,
        score,
        ob,
        fvg,
        barrida,
        estado,
        estado_dashboard,  // Operational live state (never SL/TP)
        estado_final,
        estado_historial,
        updated_at
    } = snapshot;
    
    // Dashboard live: always use the state-machine validated state (estado_final / estado_historial).
    // estado_dashboard is the raw calculated value kept only for debugging — never use it for display.
    // If the resolved candidate is a terminal/historical-only state, show SIN_SETUP instead.
    const DASHBOARD_BLOCKED = new Set(['SL', 'TP', 'DESCARTADA', 'PAUSADA']);
    const estadoCandidate = estado_final || estado_historial || estado;
    const estadoNorm = estadoCandidate ? estadoCandidate.toUpperCase().replace(/ /g, '_') : '';
    const estadoToDisplay = (!estadoNorm || DASHBOARD_BLOCKED.has(estadoNorm)) ? 'SIN_SETUP' : estadoCandidate;
    console.log("DEBUG ESTADO TO DISPLAY:", estadoToDisplay, "(raw candidate:", estadoCandidate, ")");
    
    // Format symbol (shorter name)
    const symbolShort = symbol.replace(' Index', '');
    
    // Format price
    const priceStr = price !== null ? formatPrice(price) : '--';
    
    // Format zona madre M15 with ENTRADA/STOPLOSS + copy button
    const zonaCell = formatZonaMadre(zona_madre_m15, entrada, stoploss, symbolShort);
    
    // Format estado badge using the live dashboard state
    const estadoBadge = formatEstadoBadge(estadoToDisplay);
    
    // Format score badge
    const scoreBadge = formatScoreBadge(score);
    
    // Format update time
    const timeStr = formatTime(updated_at);
    
    // Apply row color based on estado — any active/operational state gets row-activa.
    // Use estadoNorm (already uppercased + underscored) for reliable Set lookup.
    const ACTIVE_ESTADOS = new Set(['ACTIVA', 'ESPERANDO_ENTRADA', 'LLEGANDO_A_ZONA', 'EN_ZONA', 'PROFIT']);
    const rowClass = ACTIVE_ESTADOS.has(estadoNorm) ? 'row-activa' : 'row-sin-setup';
    
    return `
        <tr class="${rowClass}">
            <td><span class="symbol-name">${symbolShort}</span></td>
            <td><span class="trend-badge">${tendencia_h1}</span></td>
            <td><span class="trend-badge">${tendencia_m15}</span></td>
            <td><span class="event-label">${ultimo_evento_m15}</span></td>
            <td>${zonaCell}</td>
            <td>${scoreBadge}</td>
            <td><span class="indicator-badge">${ob}</span></td>
            <td><span class="indicator-badge">${fvg}</span></td>
            <td><span class="indicator-badge">${barrida}</span></td>
            <td>${estadoBadge}</td>
            <td><span class="price-value">${priceStr}</span></td>
            <td><span class="time-value">${timeStr}</span></td>
        </tr>
    `;
}

/**
 * Format zona madre M15 as ENTRADA / STOPLOSS with per-line copy buttons
 */
function formatZonaMadre(zona, entrada, stoploss, symbolShort) {
    const hasZona = zona && (zona.desde !== 0 || zona.hasta !== 0);
    const hasEntrada = entrada !== null && entrada !== undefined && entrada !== 0;
    const hasSL = stoploss !== null && stoploss !== undefined && stoploss !== 0;

    if (!hasZona && !hasEntrada) {
        return '<span class="zone-range">--</span>';
    }

    const entradaStr = hasEntrada ? Number(entrada).toFixed(2) : '--';
    const slStr = hasSL ? Number(stoploss).toFixed(2) : '--';
    const entradaAttr = escapeHtmlAttr(entradaStr);
    const slAttr = escapeHtmlAttr(slStr);

    return `
        <div class="zona-madre-cell">
            <div class="zona-linea">
                <span class="zona-label">ENTRADA:</span>
                <span class="zona-valor">${entradaStr}</span>
                <button class="copy-zona-btn"
                    data-value="${entradaAttr}"
                    onclick="copyZoneValue(this)"
                    aria-label="Copiar ENTRADA"
                    title="Copiar ENTRADA">&#x2398;</button>
            </div>
            <div class="zona-linea">
                <span class="zona-label">STOPLOSS:</span>
                <span class="zona-valor zona-sl">${slStr}</span>
                <button class="copy-zona-btn"
                    data-value="${slAttr}"
                    onclick="copyZoneValue(this)"
                    aria-label="Copiar STOPLOSS"
                    title="Copiar STOPLOSS">&#x2398;</button>
            </div>
        </div>
    `;
}

function escapeHtmlAttr(value) {
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

/**
 * Copy a single zone value to clipboard with visual feedback
 */
function copyZoneValue(btn) {
    const text = btn.dataset.value || '--';
    const handleSuccess = () => {
        const original = btn.textContent;
        btn.textContent = '✓';
        btn.classList.add('copy-zona-btn--copiado');
        setTimeout(() => {
            btn.textContent = original;
            btn.classList.remove('copy-zona-btn--copiado');
        }, 1500);
    };

    const handleError = (err) => {
        console.error('Error copiando al portapapeles:', err);
        const original = btn.textContent;
        btn.textContent = '!';
        setTimeout(() => {
            btn.textContent = original;
        }, 1500);
    };

    if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
        navigator.clipboard.writeText(text).then(handleSuccess).catch(handleError);
        return;
    }

    try {
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.setAttribute('readonly', '');
        textArea.style.position = 'absolute';
        textArea.style.left = '-9999px';
        document.body.appendChild(textArea);
        textArea.select();
        const copied = document.execCommand('copy');
        document.body.removeChild(textArea);
        if (copied) {
            handleSuccess();
        } else {
            handleError(new Error('document.execCommand(copy) returned false'));
        }
    } catch (err) {
        handleError(err);
    }
}

/**
 * @deprecated Use formatZonaMadre instead
 */
function formatZone(zona) {
    if (!zona || zona.desde === 0 || zona.hasta === 0) {
        return '--';
    }
    return `${zona.desde.toFixed(2)} - ${zona.hasta.toFixed(2)}`;
}

/**
 * Format estado badge for the live dashboard.
 * Only operational states are expected here (SL/TP are filtered upstream).
 */
function formatEstadoBadge(estado) {
    // Normalize estado - handle both 'SIN SETUP' and 'SIN_SETUP'
    const estadoNormalized = estado ? estado.toUpperCase().replace(/ /g, '_') : 'SIN_SETUP';
    
    // Map all possible estados to badges
    switch (estadoNormalized) {
        case 'ACTIVA':
            return '<span class="status-badge status-activa">✓ ACTIVA</span>';
        
        case 'ESPERANDO_ENTRADA':
            return '<span class="status-badge status-esperando">⏳ ESPERANDO ENTRADA</span>';
        
        case 'LLEGANDO_A_ZONA':
            return '<span class="status-badge status-llegando">↓ LLEGANDO A ZONA</span>';
        
        case 'EN_ZONA':
            return '<span class="status-badge status-en-zona">🎯 EN ZONA</span>';
        
        case 'PROFIT':
            return '<span class="status-badge status-profit">💰 PROFIT</span>';
        
        case 'TP':
            return '<span class="status-badge status-tp">✅ TP</span>';
        
        case 'SL':
            return '<span class="status-badge status-sl">❌ SL</span>';
        
        case 'PAUSADA':
            return '<span class="status-badge status-pausada">⏸ PAUSADA</span>';
        
        case 'DESCARTADA':
            return '<span class="status-badge status-descartada">🗑 DESCARTADA</span>';
        
        case 'SIN_SETUP':
        case 'SIN SETUP':
        default:
            return '<span class="status-badge status-sin-setup">○ SIN SETUP</span>';
    }
}

/**
 * Format score badge
 */
function formatScoreBadge(score) {
    let badgeClass = 'score-badge';
    if (score >= 7) {
        badgeClass += ' score-high';
    } else if (score >= 4) {
        badgeClass += ' score-medium';
    } else {
        badgeClass += ' score-low';
    }
    return `<span class="${badgeClass}">${score}</span>`;
}

/**
 * Format price value
 */
function formatPrice(price) {
    if (price === null || price === undefined) return '--';
    return price.toFixed(2);
}

/**
 * Format timestamp
 */
function formatTime(isoString) {
    try {
        const date = new Date(isoString);
        return date.toLocaleTimeString('es-ES', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    } catch (e) {
        return '--';
    }
}

/**
 * Update connection status indicator
 */
function updateConnectionStatus(connected) {
    const statusDot = document.getElementById('statusDot');
    const connectionText = document.getElementById('connectionText');
    
    if (statusDot) {
        if (connected) {
            statusDot.classList.remove('disconnected');
        } else {
            statusDot.classList.add('disconnected');
        }
    }
    
    if (connectionText) {
        connectionText.textContent = connected 
            ? 'MT5: Conectado' 
            : 'MT5: Desconectado';
    }
}

/**
 * Update last update timestamp
 */
function updateLastUpdateTime() {
    const lastUpdate = document.getElementById('lastUpdate');
    if (lastUpdate) {
        const now = new Date();
        const timeStr = now.toLocaleTimeString('es-ES', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
        lastUpdate.textContent = `Última actualización: ${timeStr}`;
    }
}

/**
 * Show error message
 */
function showError(message) {
    console.error('Error:', message);
    // Could add a toast notification here in the future
}

/**
 * Start auto-refresh
 */
function startAutoRefresh() {
    // Clear any existing interval
    if (refreshIntervalId) {
        clearInterval(refreshIntervalId);
    }
    
    // Set new interval with error handling
    refreshIntervalId = setInterval(async () => {
        try {
            await loadDashboardData();
        } catch (error) {
            console.error('Auto-refresh error:', error);
            // Continue interval even on error
        }
    }, AUTO_REFRESH_INTERVAL);
    
    console.log(`Auto-refresh started (every ${AUTO_REFRESH_INTERVAL / 1000}s)`);
}

/**
 * Stop auto-refresh
 */
function stopAutoRefresh() {
    if (refreshIntervalId) {
        clearInterval(refreshIntervalId);
        refreshIntervalId = null;
        console.log('🛑 Auto-refresh stopped');
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDashboard);
} else {
    initDashboard();
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    stopAutoRefresh();
});

console.log('✅ Dashboard script loaded');
