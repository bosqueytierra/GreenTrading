/**
 * GreenTrading Desktop - Preload Script
 * 
 * Secure bridge between Renderer and Main process
 * Exposes safe API to frontend via contextBridge
 */

const { contextBridge, ipcRenderer } = require('electron');

/**
 * Expose safe API to renderer process
 */
contextBridge.exposeInMainWorld('api', {
  /**
   * Get one candle from MT5
   * @param {string} symbol - Symbol name (e.g., "Boom 1000 Index")
   * @param {string} timeframe - Timeframe (e.g., "M15")
   * @returns {Promise<Object>} Candle data or error
   */
  getCandle: (symbol, timeframe) => {
    return ipcRenderer.invoke('get-candle', symbol, timeframe);
  },

  /**
   * Check backend status
   * @returns {Promise<Object>} Status data or error
   */
  checkStatus: () => {
    return ipcRenderer.invoke('check-status');
  }
});

console.log('✅ Preload script loaded - API exposed');
