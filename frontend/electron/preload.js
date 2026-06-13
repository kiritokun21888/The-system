/**
 * Preload bridge — exposes a minimal, safe API to the renderer. Backend URLs
 * are injected so the React app can target localhost without hard-coding.
 */
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("zero", {
  window: {
    minimize: () => ipcRenderer.invoke("window:minimize"),
    maximize: () => ipcRenderer.invoke("window:maximize"),
    close: () => ipcRenderer.invoke("window:close"),
  },
});

// Make backend endpoints discoverable to the bundled app.
contextBridge.exposeInMainWorld("ZERO_API_BASE", "http://127.0.0.1:8000");
contextBridge.exposeInMainWorld("ZERO_WS_BASE", "ws://127.0.0.1:8000/ws");
