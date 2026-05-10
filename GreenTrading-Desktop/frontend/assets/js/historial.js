console.log("HISTORIAL_JS_VERSION: FASE3B_MULTI_STRATEGY_V1");

/**
 * GreenTrading Desktop - Historial JavaScript
 * FASE 3B: Multi-strategy filter support (SMC_M15_PRO + SMC_H1_M15_PRO)
 *
 * Características:
 * - Auto-refresh cada 5 segundos
 * - Filtro por estrategia (Todas / SMC M15 PRO / SMC H1+M15 PRO)
 * - Diff-based updates (solo celdas que cambiaron)
 * - NO reconstrucción completa del DOM
 * - Preserva scroll position
 * - Preserva filtros activos
 * - Transiciones CSS suaves
 * - Sin loaders grandes
 * - Indicador discreto de conexión live
 */

// Auto-refresh interval (5 seconds)
const AUTO_REFRESH_INTERVAL = 5000;
let refreshIntervalId = null;

// Current data cache (para diff detection)
let currentData = [];

// Current filters
let currentFilters = {
    strategy: 'all',
    symbol: 'all',
    estado: 'all',
    fromDate: null,
    toDate: null
};

/**
 * Initialize historial page
 */
async function initHistorial() {
    console.log('🚀 Initializing GreenTrading Desktop Historial...');
    
    // Setup event listeners
    setupEventListeners();
    
    // Initial data load (primera vez sí construye tabla completa)
    await loadHistorialData(true);
    
    // Start auto-refresh
    startAutoRefresh();
    
    console.log('✅ Historial initialized with silent incremental updates');
}

/**
 * Setup event listeners
 */
function setupEventListeners() {
    // Manual refresh button
    const refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', async () => {
            console.log('Manual refresh triggered');
            await loadHistorialData(false); // Incremental update
        });
    }

    // Filter: Strategy
    const strategyFilter = document.getElementById('strategyFilter');
    if (strategyFilter) {
        strategyFilter.addEventListener('change', async (e) => {
            currentFilters.strategy = e.target.value;
            console.log('Strategy filter changed:', currentFilters.strategy);
            await loadHistorialData(true);
        });
    }
    
    // Filter: Symbol
    const symbolFilter = document.getElementById('symbolFilter');
    if (symbolFilter) {
        symbolFilter.addEventListener('change', async (e) => {
            currentFilters.symbol = e.target.value;
            console.log('Symbol filter changed:', currentFilters.symbol);
            await loadHistorialData(true); // Full reload on filter change
        });
    }
    
    // Filter: Estado
    const estadoFilter = document.getElementById('estadoFilter');
    if (estadoFilter) {
        estadoFilter.addEventListener('change', async (e) => {
            currentFilters.estado = e.target.value;
            console.log('Estado filter changed:', currentFilters.estado);
            await loadHistorialData(true); // Full reload on filter change
        });
    }
    
    // Date filters
    const fromDateFilter = document.getElementById('fromDate');
    const toDateFilter = document.getElementById('toDate');
    
    if (fromDateFilter) {
        fromDateFilter.addEventListener('change', async (e) => {
            currentFilters.fromDate = e.target.value;
            console.log('From date changed:', currentFilters.fromDate);
            await loadHistorialData(true); // Full reload on filter change
        });
    }
    
    if (toDateFilter) {
        toDateFilter.addEventListener('change', async (e) => {
            currentFilters.toDate = e.target.value;
            console.log('To date changed:', currentFilters.toDate);
            await loadHistorialData(true); // Full reload on filter change
        });
    }
}

/**
 * Load historial data from backend
 * 
 * @param {boolean} fullRebuild - Si true, reconstruye tabla completa. Si false, hace update incremental.
 */
async function loadHistorialData(fullRebuild = false) {
    try {
        // Build query parameters
        const params = new URLSearchParams();
        if (currentFilters.strategy !== 'all') {
            params.append('strategy_id', currentFilters.strategy);
        }
        if (currentFilters.symbol !== 'all') {
            params.append('symbol', currentFilters.symbol);
        }
        if (currentFilters.estado !== 'all') {
            params.append('estado', currentFilters.estado);
        }
        if (currentFilters.fromDate) {
            params.append('from_date', currentFilters.fromDate);
        }
        if (currentFilters.toDate) {
            params.append('to_date', currentFilters.toDate);
        }
        params.append('limit', '200');
        
        // Call API through exposed window.api
        const url = `http://127.0.0.1:8765/api/setups/history?${params.toString()}`;
        console.log(`📊 Loading historial data: ${url}`);
        
        const response = await fetch(url);
        const result = await response.json();
        
        console.log("HISTORIAL RESPONSE RAW: success=" + result.success + " count=" + (result.count || (result.setups || result.data || []).length));
        
        if (!result.success) {
            throw new Error(result.error || result.detail || 'Failed to load historial data');
        }
        
        // Support both "setups" (new) and "data" (legacy) keys
        const newData = result.setups || result.data || [];
        const closedData = newData.filter(setup => setup && (setup.estado === 'TP' || setup.estado === 'SL'));
        if (closedData.length !== newData.length) {
            console.log(`HISTORIAL FILTER: descartados ${newData.length - closedData.length} setups no cerrados`);
        }
        console.log("HISTORIAL SETUPS COUNT:", closedData.length);
        console.log(`Loaded ${closedData.length} closed setups from historial`);
        
        if (fullRebuild) {
            // First load or filter change: rebuild table
            console.log('HISTORIAL RENDER START (full rebuild)');
            buildTable(closedData);
            currentData = closedData;
            console.log('HISTORIAL RENDER DONE (full rebuild)');
        } else {
            // Incremental update: only update changed cells
            console.log('HISTORIAL RENDER START (incremental)');
            updateTableIncremental(closedData);
            currentData = closedData;
            console.log('HISTORIAL RENDER DONE (incremental)');
        }
        
        // Update statistics
        updateStatistics(closedData);
        // Update TP/SL summary (async, uses strategy filter)
        updateTPSLSummary(closedData);
        
        // Update timestamp
        updateLastUpdateTime();
        
        // Update live indicator
        updateLiveIndicator(true);
        
    } catch (error) {
        console.error('HISTORIAL RENDER ERROR:', error.message, error);
        updateLiveIndicator(false);
        showError(error.message);
    }
}

/**
 * Build complete table (used on first load or filter change)
 */
function buildTable(data) {
    const tbody = document.getElementById('historialTableBody');
    if (!tbody) {
        console.error('Table body not found');
        return;
    }
    
    // Save current scroll position
    const container = tbody.closest('.table-container');
    const scrollTop = container ? container.scrollTop : 0;
    
    // Clear table
    tbody.innerHTML = '';
    
    if (data.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="10" style="text-align: center; padding: 20px; color: #6b7280;">
                    No hay setups en el historial
                </td>
            </tr>
        `;
        return;
    }
    
    // Build rows
    data.forEach(setup => {
        const row = createTableRow(setup);
        tbody.appendChild(row);
    });
    
    // Restore scroll position
    if (container) {
        container.scrollTop = scrollTop;
    }
}

/**
 * Update table incrementally (silent update - NO full rebuild)
 * 
 * Estrategia:
 * 1. Comparar newData con currentData
 * 2. Identificar cambios (por ID)
 * 3. Actualizar solo las celdas que cambiaron
 * 4. NO tocar el DOM innecesariamente
 * 5. Aplicar transiciones CSS suaves
 */
function updateTableIncremental(newData) {
    const tbody = document.getElementById('historialTableBody');
    if (!tbody) return;
    
    // Save scroll position
    const container = tbody.closest('.table-container');
    const scrollTop = container ? container.scrollTop : 0;
    
    // Create maps for fast lookup
    const currentMap = new Map(currentData.map(s => [s.id, s]));
    const newMap = new Map(newData.map(s => [s.id, s]));
    
    // Update existing rows
    newData.forEach(newSetup => {
        const setupId = newSetup.id;
        const oldSetup = currentMap.get(setupId);
        
        // Find existing row
        const row = tbody.querySelector(`tr[data-setup-id="${setupId}"]`);
        
        if (!row) {
            // New setup: add row at top (silent insert)
            const newRow = createTableRow(newSetup);
            tbody.insertBefore(newRow, tbody.firstChild);
            // Fade in animation
            setTimeout(() => newRow.classList.add('row-fade-in'), 10);
            return;
        }
        
        if (!oldSetup) {
            // Should not happen, but update full row
            updateRowCells(row, newSetup);
            return;
        }
        
        // Compare fields and update only changed cells
        updateCellIfChanged(row, 'estado-dashboard', oldSetup.estado_dashboard, newSetup.estado_dashboard, (cell, value) => {
            cell.textContent = value || '--';
            cell.className = 'estado-badge ' + getEstadoBadgeClass(value);
        });
        updateCellIfChanged(row, 'estado', oldSetup.estado, newSetup.estado, (cell, value) => {
            cell.textContent = value || '--';
            cell.className = 'estado-badge ' + getEstadoBadgeClass(value);
        });
        updateCellIfChanged(row, 'resultado-puntos', oldSetup.resultado_puntos, newSetup.resultado_puntos, (cell, value) => {
            const formatted = value != null ? (value > 0 ? `+${value}` : value) : '--';
            cell.textContent = formatted;
            cell.className = 'resultado-puntos ' + (value > 0 ? 'resultado-positive' : value < 0 ? 'resultado-negative' : '');
        });
    });
    
    // Remove deleted rows (setups that no longer match filter)
    currentData.forEach(oldSetup => {
        if (!newMap.has(oldSetup.id)) {
            const row = tbody.querySelector(`tr[data-setup-id="${oldSetup.id}"]`);
            if (row) {
                row.classList.add('row-fade-out');
                setTimeout(() => row.remove(), 300);
            }
        }
    });
    
    // Restore scroll position (mantener posición visual)
    if (container) {
        container.scrollTop = scrollTop;
    }
}

/**
 * Update a cell if value changed
 * 
 * @param {HTMLElement} row - Table row
 * @param {string} cellClass - Cell class name
 * @param {any} oldValue - Old value
 * @param {any} newValue - New value
 * @param {Function} updateFn - Optional custom update function
 */
function updateCellIfChanged(row, cellClass, oldValue, newValue, updateFn = null) {
    if (oldValue === newValue) return;
    
    const cell = row.querySelector(`.${cellClass}`);
    if (!cell) return;
    
    // Add highlight animation
    cell.classList.add('cell-update-highlight');
    setTimeout(() => cell.classList.remove('cell-update-highlight'), 600);
    
    // Update value
    if (updateFn) {
        updateFn(cell, newValue);
    } else {
        cell.textContent = newValue != null ? newValue : '--';
    }
}

/**
 * Update all cells in a row (fallback)
 */
function updateRowCells(row, setup) {
    row.innerHTML = createTableRow(setup).innerHTML;
}

/**
 * Create a table row for a setup
 */
function createTableRow(setup) {
    const tr = document.createElement('tr');
    tr.setAttribute('data-setup-id', setup.id);
    
    // Determine row type for background tinting
    const symbol = (setup.symbol || '').toLowerCase();
    if (symbol.includes('boom')) {
        tr.setAttribute('data-type', 'boom');
    } else if (symbol.includes('crash')) {
        tr.setAttribute('data-type', 'crash');
    }
    
    const estadoDashboardClass = getEstadoBadgeClass(setup.estado_dashboard);
    const estadoClass = getEstadoBadgeClass(setup.estado);
    
    const resultadoPuntos = setup.resultado_puntos != null 
        ? (setup.resultado_puntos > 0 ? `+${setup.resultado_puntos}` : setup.resultado_puntos)
        : '--';
    const resultadoClass = setup.resultado_puntos > 0 ? 'resultado-positive' : 
                          setup.resultado_puntos < 0 ? 'resultado-negative' : '';
    
    const contexto = [
        setup.tendencia_h1 || '',
        setup.tendencia_m15 || '',
        setup.ultimo_evento_m15 || ''
    ].filter(Boolean).join(' / ') || '--';
    
    tr.innerHTML = `
        <td>${formatDate(setup.created_at)}</td>
        <td>${setup.symbol || '--'}</td>
        <td>${setup.strategy_name || '--'}</td>
        <td>${setup.entrada != null ? setup.entrada.toFixed(2) : '--'}</td>
        <td class="stoploss-cell">${setup.stoploss != null ? setup.stoploss.toFixed(2) : '--'}</td>
        <td>${setup.tp_1_1 != null ? setup.tp_1_1.toFixed(2) : '--'}</td>
        <td><span class="estado-badge ${estadoDashboardClass} estado-dashboard">${setup.estado_dashboard || '--'}</span></td>
        <td><span class="estado-badge ${estadoClass} estado">${setup.estado || '--'}</span></td>
        <td class="resultado-puntos ${resultadoClass}">${resultadoPuntos}</td>
        <td class="contexto-cell">${contexto}</td>
    `;
    
    return tr;
}

/**
 * Get badge class for estado
 */
function getEstadoBadgeClass(estado) {
    if (!estado) return '';
    
    const estadoMap = {
        'ACTIVA': 'badge-blue',
        'SIN_SETUP': 'badge-gray',
        'ESPERANDO_ENTRADA': 'badge-blue',
        'LLEGANDO_A_ZONA': 'badge-yellow',
        'EN_ZONA': 'badge-purple',
        'PROFIT': 'badge-green',
        'TP': 'badge-green-solid',
        'SL': 'badge-red',
        'DESCARTADA': 'badge-gray'
    };
    
    return estadoMap[estado] || 'badge-gray';
}

/**
 * Format date (DD/MM/YYYY HH:MM)
 */
function formatDate(isoString) {
    if (!isoString) return '--';
    const date = new Date(isoString);
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const year = date.getFullYear();
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return `${day}/${month}/${year} ${hours}:${minutes}`;
}

/**
 * Format timestamp (HH:MM:SS)
 */
function formatTimestamp(isoString) {
    if (!isoString) return '--';
    const date = new Date(isoString);
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const seconds = String(date.getSeconds()).padStart(2, '0');
    return `${hours}:${minutes}:${seconds}`;
}

/**
 * Update statistics panel
 */
function updateStatistics(data) {
    // Total setups
    const totalElement = document.getElementById('totalSetups');
    if (totalElement) {
        totalElement.textContent = data.length;
    }
    
    // Count by estado
    const estadoCounts = data.reduce((acc, setup) => {
        const estado = setup.estado || 'UNKNOWN';
        acc[estado] = (acc[estado] || 0) + 1;
        return acc;
    }, {});
    
    // Update badges
    ['TP', 'SL', 'PROFIT', 'EN_ZONA'].forEach(estado => {
        const element = document.getElementById(`count${estado.replace('_', '')}`);
        if (element) {
            element.textContent = estadoCounts[estado] || 0;
        }
    });
}


/**
 * Update TP/SL summary by symbol — uses /api/setups/summary?strategy_id=...
 */
async function updateTPSLSummary(data) {
    const summaryContainer = document.getElementById('tpslSummary');
    if (!summaryContainer) return;

    try {
        const params = new URLSearchParams();
        if (currentFilters.strategy !== 'all') {
            params.append('strategy_id', currentFilters.strategy);
        }
        const url = `http://127.0.0.1:8765/api/setups/summary?${params.toString()}`;
        const response = await fetch(url);
        const result = await response.json();

        if (!result.success) throw new Error(result.error || 'Summary error');

        const symbolStats = result.data || {};

        let html = '<div class="summary-grid">';
        Object.keys(symbolStats).sort().forEach(symbol => {
            const stats = symbolStats[symbol];
            if (stats.tp > 0 || stats.sl > 0) {
                const total = stats.tp + stats.sl;
                const winrate = total > 0 ? Math.round((stats.tp / total) * 100) : 0;
                html += `
                    <div class="summary-item">
                        <div class="summary-symbol">${symbol}</div>
                        <div class="summary-stats">
                            <span class="tp-count">TP: ${stats.tp}</span>
                            <span class="sl-count">SL: ${stats.sl}</span>
                            <span class="winrate-count">Win: ${winrate}%</span>
                        </div>
                    </div>
                `;
            }
        });
        html += '</div>';
        summaryContainer.innerHTML = html;

    } catch (err) {
        console.error('SUMMARY ERROR:', err.message);
        // Fallback: calcular localmente desde data
        _updateTPSLSummaryLocal(data, summaryContainer);
    }
}

function _updateTPSLSummaryLocal(data, summaryContainer) {
    const symbolStats = data.reduce((acc, setup) => {
        const symbol = setup.symbol || 'Unknown';
        if (!acc[symbol]) acc[symbol] = { tp: 0, sl: 0 };
        if (setup.estado === 'TP') acc[symbol].tp++;
        else if (setup.estado === 'SL') acc[symbol].sl++;
        return acc;
    }, {});

    let html = '<div class="summary-grid">';
    Object.keys(symbolStats).sort().forEach(symbol => {
        const stats = symbolStats[symbol];
        if (stats.tp > 0 || stats.sl > 0) {
            const total = stats.tp + stats.sl;
            const winrate = total > 0 ? Math.round((stats.tp / total) * 100) : 0;
            html += `
                <div class="summary-item">
                    <div class="summary-symbol">${symbol}</div>
                    <div class="summary-stats">
                        <span class="tp-count">TP: ${stats.tp}</span>
                        <span class="sl-count">SL: ${stats.sl}</span>
                        <span class="winrate-count">Win: ${winrate}%</span>
                    </div>
                </div>
            `;
        }
    });
    html += '</div>';
    summaryContainer.innerHTML = html;
}

/**
 * Update last update time
 */
function updateLastUpdateTime() {
    const element = document.getElementById('lastUpdate');
    if (element) {
        const now = new Date();
        const timeStr = now.toLocaleTimeString('es-ES');
        element.textContent = `Última actualización: ${timeStr}`;
    }
}

/**
 * Update live indicator (discrete pulsating dot)
 */
function updateLiveIndicator(isConnected) {
    const indicator = document.getElementById('liveIndicator');
    if (indicator) {
        if (isConnected) {
            indicator.className = 'live-indicator live-indicator-active';
            indicator.title = 'Conectado - Actualizando cada 5s';
        } else {
            indicator.className = 'live-indicator live-indicator-error';
            indicator.title = 'Error de conexión';
        }
    }
}

/**
 * Show error message in the table body
 */
function showError(message) {
    console.error('Error:', message);
    const tbody = document.getElementById('historialTableBody');
    if (tbody) {
        tbody.innerHTML = `
            <tr>
                <td colspan="10" style="text-align: center; padding: 40px; color: #ef4444;">
                    Error cargando historial: ${message}
                </td>
            </tr>
        `;
    }
}

/**
 * Start auto-refresh
 */
function startAutoRefresh() {
    if (refreshIntervalId) {
        clearInterval(refreshIntervalId);
    }
    
    refreshIntervalId = setInterval(async () => {
        console.log('🔄 Auto-refresh triggered (incremental)');
        await loadHistorialData(false); // Incremental update
    }, AUTO_REFRESH_INTERVAL);
    
    console.log(`✅ Auto-refresh started: every ${AUTO_REFRESH_INTERVAL / 1000}s (silent incremental)`);
}

/**
 * Stop auto-refresh
 */
function stopAutoRefresh() {
    if (refreshIntervalId) {
        clearInterval(refreshIntervalId);
        refreshIntervalId = null;
        console.log('⏹️ Auto-refresh stopped');
    }
}

// Initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initHistorial);
} else {
    initHistorial();
}
