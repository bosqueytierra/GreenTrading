/**
 * GreenTrading Desktop - Frontend JavaScript
 * Phase 1: Minimal UI logic for proof of concept
 */

console.log('✅ Frontend script loaded');

// DOM elements
let pythonStatus, mt5Status, getCandleBtn, refreshStatusBtn;
let symbolSelect, timeframeSelect, resultSection, candleDisplay, errorDisplay;

/**
 * Initialize app when DOM is ready
 */
document.addEventListener('DOMContentLoaded', () => {
    console.log('🎯 Initializing frontend...');
    
    // Get DOM elements
    pythonStatus = document.getElementById('python-status');
    mt5Status = document.getElementById('mt5-status');
    getCandleBtn = document.getElementById('get-candle-btn');
    refreshStatusBtn = document.getElementById('refresh-status');
    symbolSelect = document.getElementById('symbol-select');
    timeframeSelect = document.getElementById('timeframe-select');
    resultSection = document.getElementById('result-section');
    candleDisplay = document.getElementById('candle-display');
    errorDisplay = document.getElementById('error-display');
    
    // Setup event listeners
    getCandleBtn.addEventListener('click', handleGetCandle);
    refreshStatusBtn.addEventListener('click', checkStatus);
    
    // Initial status check
    setTimeout(() => {
        checkStatus();
    }, 1000);
    
    console.log('✅ Frontend initialized');
});

/**
 * Check backend and MT5 status
 */
async function checkStatus() {
    console.log('🔍 Checking status...');
    
    pythonStatus.textContent = '⏳ Checking...';
    pythonStatus.className = 'value';
    mt5Status.textContent = '⏳ Checking...';
    mt5Status.className = 'value';
    
    try {
        const result = await window.api.checkStatus();
        
        if (result.success) {
            const { backend_running, mt5_connected, mt5_terminal_info } = result.data;
            
            // Update Python status
            if (backend_running) {
                pythonStatus.textContent = '✅ Connected';
                pythonStatus.className = 'value status-ok';
            } else {
                pythonStatus.textContent = '❌ Not Running';
                pythonStatus.className = 'value status-error';
            }
            
            // Update MT5 status
            if (mt5_connected) {
                mt5Status.textContent = `✅ Connected - ${mt5_terminal_info || 'MT5'}`;
                mt5Status.className = 'value status-ok';
            } else {
                mt5Status.textContent = '❌ Disconnected';
                mt5Status.className = 'value status-error';
            }
        } else {
            throw new Error(result.error);
        }
    } catch (error) {
        console.error('❌ Status check failed:', error);
        pythonStatus.textContent = '❌ Error';
        pythonStatus.className = 'value status-error';
        mt5Status.textContent = '❌ Unknown';
        mt5Status.className = 'value status-error';
        showError(`Failed to check status: ${error.message}`);
    }
}

/**
 * Handle get candle button click
 */
async function handleGetCandle() {
    console.log('📈 Getting candle from MT5...');
    
    const symbol = symbolSelect.value;
    const timeframe = timeframeSelect.value;
    
    // Disable button
    getCandleBtn.disabled = true;
    getCandleBtn.textContent = '⏳ Loading...';
    
    // Hide previous results/errors
    resultSection.style.display = 'none';
    errorDisplay.style.display = 'none';
    
    try {
        const result = await window.api.getCandle(symbol, timeframe);
        
        if (result.success) {
            displayCandle(result.data);
        } else {
            throw new Error(result.error);
        }
    } catch (error) {
        console.error('❌ Failed to get candle:', error);
        showError(`Failed to get candle: ${error.message}`);
    } finally {
        // Re-enable button
        getCandleBtn.disabled = false;
        getCandleBtn.textContent = '📈 Get Candle from MT5';
    }
}

/**
 * Display candle data
 */
function displayCandle(data) {
    console.log('📊 Displaying candle:', data);
    
    const { symbol, timeframe, candle } = data;
    
    if (!candle) {
        showError('No candle data received');
        return;
    }
    
    // Format candle display
    const html = `
        <div class="candle-field">
            <span class="field-label">Symbol:</span>
            <span class="field-value">${symbol}</span>
        </div>
        <div class="candle-field">
            <span class="field-label">Timeframe:</span>
            <span class="field-value">${timeframe}</span>
        </div>
        <div class="candle-field">
            <span class="field-label">Time:</span>
            <span class="field-value">${candle.time}</span>
        </div>
        <div class="candle-field">
            <span class="field-label">Open:</span>
            <span class="field-value">${candle.open}</span>
        </div>
        <div class="candle-field">
            <span class="field-label">High:</span>
            <span class="field-value">${candle.high}</span>
        </div>
        <div class="candle-field">
            <span class="field-label">Low:</span>
            <span class="field-value">${candle.low}</span>
        </div>
        <div class="candle-field">
            <span class="field-label">Close:</span>
            <span class="field-value">${candle.close}</span>
        </div>
        <div class="candle-field">
            <span class="field-label">Volume:</span>
            <span class="field-value">${candle.tick_volume}</span>
        </div>
    `;
    
    candleDisplay.innerHTML = html;
    resultSection.style.display = 'block';
}

/**
 * Show error message
 */
function showError(message) {
    errorDisplay.textContent = `❌ Error: ${message}`;
    errorDisplay.style.display = 'block';
}
