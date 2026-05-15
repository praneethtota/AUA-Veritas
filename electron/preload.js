/**
 * electron/preload.js — Secure IPC bridge.
 *
 * Exposes a minimal, typed API to the renderer via contextBridge.
 * The renderer never has direct access to Node.js or Electron APIs.
 *
 * Available in renderer as: window.veritas.*
 */

const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('veritas', {
  // ── App info ───────────────────────────────────────────────────────────────
  getVersion: () => ipcRenderer.invoke('get-version'),

  // ── API communication ──────────────────────────────────────────────────────
  apiStatus: () => ipcRenderer.invoke('api-status'),

  apiRequest: (method, path, body) =>
    ipcRenderer.invoke('api-request', { method, path, body }),

  // ── Events from main process ───────────────────────────────────────────────
  onApiReady: (callback) => {
    ipcRenderer.on('api-ready', callback)
    return () => ipcRenderer.removeListener('api-ready', callback)
  },

  // ── Shell ──────────────────────────────────────────────────────────────────
  openExternal: (url) => ipcRenderer.invoke('open-external', url),

  // ── Window management ──────────────────────────────────────────────────────
  minimizeToTray: () => ipcRenderer.invoke('minimize-to-tray'),

  // ── Environment ───────────────────────────────────────────────────────────
  platform: process.platform,
  isDev: process.env.NODE_ENV !== 'production',
})
