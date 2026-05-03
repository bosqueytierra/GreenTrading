// Configuración de Supabase
// IMPORTANTE: Reemplazar estas credenciales con las reales de tu proyecto Supabase
// Puedes usar config.example.js como plantilla y crear tu propio config.js
const SUPABASE_URL = 'YOUR_SUPABASE_URL';
const SUPABASE_ANON_KEY = 'YOUR_SUPABASE_ANON_KEY';

// Variables globales
let autoRefreshInterval = null;
const AUTO_REFRESH_SECONDS = 30;

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

function initializeApp() {
    // Verificar configuración
    if (SUPABASE_URL === 'YOUR_SUPABASE_URL' || SUPABASE_ANON_KEY === 'YOUR_SUPABASE_ANON_KEY') {
        updateStatus('⚠️ Configurar SUPABASE_URL y SUPABASE_ANON_KEY en assets/app.js', 'warning');
        return;
    }

    // Event listeners
    document.getElementById('symbolSelect').addEventListener('change', fetchData);
    document.getElementById('timeframeSelect').addEventListener('change', fetchData);
    document.getElementById('refreshBtn').addEventListener('click', fetchData);

    // Cargar datos iniciales
    fetchData();

    // Iniciar auto-refresh
    startAutoRefresh();
}

function startAutoRefresh() {
    // Limpiar intervalo existente
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
    }

    // Configurar nuevo intervalo
    autoRefreshInterval = setInterval(() => {
        fetchData(true);
    }, AUTO_REFRESH_SECONDS * 1000);

    updateStatus(`Auto-refresh cada ${AUTO_REFRESH_SECONDS} segundos activado`, 'success');
}

function updateStatus(message, type = 'info') {
    const statusElement = document.getElementById('statusMessage');
    statusElement.textContent = message;
    
    // Opcional: cambiar color según tipo
    if (type === 'error') {
        statusElement.style.color = 'var(--accent-red)';
    } else if (type === 'success') {
        statusElement.style.color = 'var(--accent-green)';
    } else if (type === 'warning') {
        statusElement.style.color = '#f0ad4e';
    } else {
        statusElement.style.color = 'var(--text-secondary)';
    }
}

async function fetchData(isAutoRefresh = false) {
    const symbol = document.getElementById('symbolSelect').value;
    const timeframe = document.getElementById('timeframeSelect').value;

    if (!isAutoRefresh) {
        updateStatus('Cargando datos...', 'info');
    }

    try {
        // Construir URL de Supabase con filtros y orden
        const url = `${SUPABASE_URL}/rest/v1/market_candles?symbol=eq.${encodeURIComponent(symbol)}&timeframe=eq.${timeframe}&order=timestamp.desc&limit=10`;

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

        if (!data || data.length === 0) {
            updateStatus('No hay datos disponibles para este símbolo/timeframe', 'warning');
            clearDisplay();
            return;
        }

        // Actualizar display con la última vela (más reciente)
        updateDisplay(data[0], symbol, timeframe);

        // Actualizar tabla con las últimas 10 velas
        updateTable(data);

        // Actualizar timestamp de última actualización
        updateLastUpdateTime();

        if (!isAutoRefresh) {
            updateStatus('✅ Datos actualizados correctamente', 'success');
        }

    } catch (error) {
        console.error('Error fetching data:', error);
        updateStatus(`❌ Error: ${error.message}`, 'error');
    }
}

function updateDisplay(candle, symbol, timeframe) {
    document.getElementById('displaySymbol').textContent = symbol;
    document.getElementById('displayTimeframe').textContent = timeframe;
    document.getElementById('closePrice').textContent = formatPrice(candle.close);
    document.getElementById('highPrice').textContent = formatPrice(candle.high);
    document.getElementById('lowPrice').textContent = formatPrice(candle.low);
    document.getElementById('timestamp').textContent = formatTimestamp(candle.timestamp);
}

function updateTable(candles) {
    const tbody = document.getElementById('candlesTableBody');
    tbody.innerHTML = '';

    candles.forEach(candle => {
        const row = document.createElement('tr');
        
        // Determinar si es alcista o bajista
        const isBullish = candle.close >= candle.open;
        const closeClass = isBullish ? 'bullish' : 'bearish';

        row.innerHTML = `
            <td>${formatTimestamp(candle.timestamp)}</td>
            <td>${formatPrice(candle.open)}</td>
            <td>${formatPrice(candle.high)}</td>
            <td>${formatPrice(candle.low)}</td>
            <td class="${closeClass}">${formatPrice(candle.close)}</td>
            <td>${formatVolume(candle.tick_volume)}</td>
        `;
        
        tbody.appendChild(row);
    });
}

function clearDisplay() {
    document.getElementById('displaySymbol').textContent = '--';
    document.getElementById('displayTimeframe').textContent = '--';
    document.getElementById('closePrice').textContent = '--';
    document.getElementById('highPrice').textContent = '--';
    document.getElementById('lowPrice').textContent = '--';
    document.getElementById('timestamp').textContent = '--';
    
    const tbody = document.getElementById('candlesTableBody');
    tbody.innerHTML = '<tr><td colspan="6" class="loading">No hay datos disponibles</td></tr>';
}

function updateLastUpdateTime() {
    const now = new Date();
    const timeString = now.toLocaleTimeString('es-ES', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
    document.getElementById('lastUpdate').textContent = timeString;
}

function formatPrice(price) {
    if (price === null || price === undefined) return '--';
    return parseFloat(price).toFixed(5);
}

function formatVolume(volume) {
    if (volume === null || volume === undefined) return '--';
    const numValue = Number(volume);
    if (isNaN(numValue)) return '--';
    return Math.round(numValue).toLocaleString('es-ES');
}

function formatTimestamp(timestamp) {
    if (!timestamp) return '--';
    
    try {
        const date = new Date(timestamp);
        return date.toLocaleString('es-ES', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    } catch (error) {
        return timestamp;
    }
}

// Cleanup al cerrar/recargar página
window.addEventListener('beforeunload', () => {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
    }
});
