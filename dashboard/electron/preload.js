// Preload bridge — exposes a minimal, safe API to the renderer.

import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("swarmAPI", {
  minimize: () => ipcRenderer.send("win:minimize"),
  maximize: () => ipcRenderer.send("win:maximize"),
  close: () => ipcRenderer.send("win:close"),
  /** Subscribe to deep-link / tray navigation events. */
  onNavigate: (cb) => {
    ipcRenderer.removeAllListeners("navigate");
    ipcRenderer.on("navigate", (_e, view) => cb(view));
  },
});
