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
  },

  /**
   * Get snapshot of all dashboard symbols (Phase 2)
   * @returns {Promise<Object>} Array of symbol snapshots or error
   */
  getSymbolsSnapshot: () => {
    return ipcRenderer.invoke('get-symbols-snapshot');
  },

  /**
   * Get SMC M15 PRO snapshot (Phase 3)
   * @returns {Promise<Object>} Array of SMC analysis snapshots or error
   */
  getSmcM15ProSnapshot: () => {
    return ipcRenderer.invoke('get-smc-m15-pro-snapshot');
  },

  /**
   * Get SMC H1+M15 PRO snapshot (FASE 3B)
   * @returns {Promise<Object>} Array of SMC H1+M15 analysis snapshots or error
   */
  getSmcH1M15ProSnapshot: () => {
    return ipcRenderer.invoke('get-smc-h1m15-pro-snapshot');
  }
});

console.log('✅ Preload script loaded - API exposed');
