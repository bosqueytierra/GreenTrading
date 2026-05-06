/**
 * GreenTrading Desktop - Dashboard JavaScript
 * Phase 2: Real-time dashboard with MT5 data
 */

// Auto-refresh interval (10 seconds)
const AUTO_REFRESH_INTERVAL = 10000;
let refreshIntervalId = null;

// Symbols configuration
const BOOM_SYMBOLS = [
    "Boom 1000 Index",
    "Boom 900 Index",
    "Boom 600 Index",
    "Boom 500 Index",
    "Boom 300 Index"
];

const CRASH_SYMBOLS = [
    "Crash 1000 Index",
    "Crash 900 Index",
    "Crash 600 Index",
    "Crash 500 Index",
    "Crash 300 Index"
];

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
    console.log('📊 Loading dashboard data...');
    
    try {
        // Call API through exposed window.api
        const result = await window.api.getSymbolsSnapshot();
        
        if (!result.success) {
            throw new Error(result.error || 'Failed to load data');
        }
        
        const snapshots = result.data;
        console.log(`✅ Loaded ${snapshots.length} symbol snapshots`);
        
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
        console.error('❌ Error loading dashboard data:', error);
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
                <td colspan="7" class="loading-cell" style="text-align: center; padding: 20px;">
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
 * Create table row for a symbol snapshot
 */
function createTableRow(snapshot) {
    const {
        symbol,
        price,
        m1_last_candle,
        m15_last_candle,
        h1_last_candle,
        mt5_connected,
        updated_at
    } = snapshot;
    
    // Format price
    const priceStr = price !== null ? formatPrice(price) : '--';
    
    // Format candles
    const m1Str = formatCandle(m1_last_candle);
    const m15Str = formatCandle(m15_last_candle);
    const h1Str = formatCandle(h1_last_candle);
    
    // Format status
    const statusBadge = mt5_connected
        ? '<span class="status-badge status-connected">✓ Conectado</span>'
        : '<span class="status-badge status-disconnected">✗ Desconectado</span>';
    
    // Format update time
    const timeStr = formatTime(updated_at);
    
    return `
        <tr>
            <td><span class="symbol-name">${symbol}</span></td>
            <td><span class="price-value">${priceStr}</span></td>
            <td>${m1Str}</td>
            <td>${m15Str}</td>
            <td>${h1Str}</td>
            <td>${statusBadge}</td>
            <td>${timeStr}</td>
        </tr>
    `;
}

/**
 * Format price value
 */
function formatPrice(price) {
    if (price === null || price === undefined) return '--';
    return price.toFixed(2);
}

/**
 * Format candle data
 */
function formatCandle(candle) {
    if (!candle) {
        return '<span class="candle-data">--</span>';
    }
    
    const close = candle.close ? candle.close.toFixed(2) : '--';
    const time = candle.time ? formatCandleTime(candle.time) : '';
    
    return `
        <div class="candle-data">
            <span class="candle-price">${close}</span>
            ${time ? `<span class="candle-time">${time}</span>` : ''}
        </div>
    `;
}

/**
 * Format candle time (just time, no date)
 */
function formatCandleTime(isoString) {
    try {
        const date = new Date(isoString);
        return date.toLocaleTimeString('es-ES', {
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch (e) {
        return '';
    }
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
    
    // Set new interval
    refreshIntervalId = setInterval(async () => {
        console.log('⏰ Auto-refresh triggered');
        await loadDashboardData();
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
