// Electron main process — frameless, fullscreen mission-control window with a
// system tray, a global show/hide shortcut, deep-link routing, single-instance
// lock, and an optional auto-launch toggle.

import { app, BrowserWindow, Tray, Menu, globalShortcut, ipcMain, nativeImage } from "electron";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DEV_URL = process.env.VITE_DEV_SERVER;

/** @type {BrowserWindow | null} */
let win = null;
/** @type {Tray | null} */
let tray = null;

// ---- Single instance lock ----
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on("second-instance", (_e, argv) => {
    if (win) {
      if (win.isMinimized()) win.restore();
      win.show();
      win.focus();
      handleDeepLink(argv.find((a) => a.startsWith("system://")));
    }
  });
}

// ---- Deep link registration (system://dashboard, system://memory, …) ----
if (process.defaultApp && process.argv.length >= 2) {
  app.setAsDefaultProtocolClient("system", process.execPath, [path.resolve(process.argv[1])]);
} else {
  app.setAsDefaultProtocolClient("system");
}

function handleDeepLink(url) {
  if (!url || !win) return;
  const view = url.replace("system://", "").replace(/\/$/, "");
  win.webContents.send("navigate", view);
}

function createWindow() {
  win = new BrowserWindow({
    width: 1600,
    height: 1000,
    minWidth: 1100,
    minHeight: 720,
    frame: false, // frameless — custom title bar in the renderer
    fullscreen: true,
    backgroundColor: "#02040A",
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (DEV_URL) {
    win.loadURL(DEV_URL);
  } else {
    win.loadFile(path.join(__dirname, "..", "dist", "index.html"));
  }

  win.once("ready-to-show", () => win?.show());
  win.on("closed", () => (win = null));
}

function createTray() {
  // A 1x1 transparent base image; replace with a real icon asset in production.
  const icon = nativeImage.createEmpty();
  tray = new Tray(icon);
  tray.setToolTip("Swarm Mission Control");
  const menu = Menu.buildFromTemplate([
    { label: "Dashboard", click: () => navigate("dashboard") },
    { label: "Memory", click: () => navigate("memory") },
    { label: "Agents", click: () => navigate("agents") },
    { label: "Performance", click: () => navigate("performance") },
    { type: "separator" },
    { label: "Show / Hide", click: toggleWindow },
    { label: "Quit", click: () => app.quit() },
  ]);
  tray.setContextMenu(menu);
  tray.on("click", toggleWindow);
}

function navigate(view) {
  if (!win) return;
  win.show();
  win.webContents.send("navigate", view);
}

function toggleWindow() {
  if (!win) return;
  if (win.isVisible()) win.hide();
  else {
    win.show();
    win.focus();
  }
}

// ---- IPC from the renderer title bar ----
ipcMain.on("win:minimize", () => win?.minimize());
ipcMain.on("win:maximize", () => {
  if (!win) return;
  win.isMaximized() ? win.unmaximize() : win.maximize();
});
ipcMain.on("win:close", () => win?.close());

app.whenReady().then(() => {
  createWindow();
  createTray();

  // Global show/hide shortcut.
  globalShortcut.register("CommandOrControl+Shift+S", toggleWindow);

  // macOS deep links.
  app.on("open-url", (event, url) => {
    event.preventDefault();
    handleDeepLink(url);
  });

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

// Optional auto-launch on system startup (disabled by default; flip to true).
app.setLoginItemSettings({ openAtLogin: false, name: "Swarm Mission Control" });

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("will-quit", () => globalShortcut.unregisterAll());
