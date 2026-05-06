console.log("DASHBOARD_JS_VERSION: DEBUG_MAPPING_V2");

/**
 * GreenTrading Desktop - Dashboard JavaScript
 * Phase 3: SMC M15 PRO dashboard with real-time SMC analysis
 */

// Auto-refresh interval (5 seconds)
const AUTO_REFRESH_INTERVAL = 5000;
let refreshIntervalId = null;

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
    console.log('📊 Loading SMC M15 PRO dashboard data...');
    
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
        console.log(`✅ Loaded ${snapshots.length} SMC snapshots`);
        
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
        console.error('❌ Error loading SMC dashboard data:', error);
        updateConnectionStatus(false);
        showError(error.message);
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
    
    const {
        symbol,
        price,
        tendencia_h1,
        tendencia_m15,
        ultimo_evento_m15,
        zona_madre_m15,
        score,
        ob,
        fvg,
        barrida,
        estado,
        updated_at
    } = snapshot;
    
    // Format symbol (shorter name)
    const symbolShort = symbol.replace(' Index', '');
    
    // Format price
    const priceStr = price !== null ? formatPrice(price) : '--';
    
    // Format zone
    const zoneStr = formatZone(zona_madre_m15);
    
    // Format estado badge
    const estadoBadge = formatEstadoBadge(estado);
    
    // Format score badge
    const scoreBadge = formatScoreBadge(score);
    
    // Format update time
    const timeStr = formatTime(updated_at);
    
    // Apply row color based on estado
    const rowClass = estado === 'ACTIVA' ? 'row-activa' : 'row-sin-setup';
    
    return `
        <tr class="${rowClass}">
            <td><span class="symbol-name">${symbolShort}</span></td>
            <td><span class="trend-badge">${tendencia_h1}</span></td>
            <td><span class="trend-badge">${tendencia_m15}</span></td>
            <td><span class="event-label">${ultimo_evento_m15}</span></td>
            <td><span class="zone-range">${zoneStr}</span></td>
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
 * Format zone range
 */
function formatZone(zona) {
    if (!zona || zona.desde === 0 || zona.hasta === 0) {
        return '--';
    }
    return `${zona.desde.toFixed(2)} - ${zona.hasta.toFixed(2)}`;
}

/**
 * Format estado badge
 */
function formatEstadoBadge(estado) {
    if (estado === 'ACTIVA') {
        return '<span class="status-badge status-activa">✓ ACTIVA</span>';
    }
    return '<span class="status-badge status-sin-setup">○ SIN SETUP</span>';
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
            console.log('⏰ Auto-refresh triggered');
            await loadDashboardData();
        } catch (error) {
            console.error('❌ Auto-refresh error:', error);
            // Continue interval even on error
        }
    }, AUTO_REFRESH_INTERVAL);
    
    console.log(`✅ Auto-refresh started (every ${AUTO_REFRESH_INTERVAL / 1000}s)`);
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
