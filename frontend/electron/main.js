/**
 * Electron main process for Z.E.R.O.
 *
 * Responsibilities:
 *  - Spawn the Python FastAPI backend as a child process.
 *  - Create the frameless, dark desktop window.
 *  - Load the Vite dev server in development, or the built bundle in prod.
 *  - Tear the backend down cleanly on quit.
 */
const { app, BrowserWindow, ipcMain, shell } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const http = require("http");

// Dev mode only when explicitly launched against the Vite dev server.
// `npm run desktop` and the packaged app both load the built bundle.
const isDev = process.env.ZERO_DEV === "1";
const BACKEND_PORT = 8000;

let mainWindow = null;
let backendProc = null;

function backendDir() {
  // Packaged: backend ships in resources/backend. Source: ../../backend.
  return app.isPackaged
    ? path.join(process.resourcesPath, "backend")
    : path.join(__dirname, "..", "..", "backend");
}

function resolvePython() {
  // Prefer a project virtualenv if present, else fall back to system python.
  const venvDir = process.platform === "win32" ? "Scripts" : "bin";
  const venvPython = process.platform === "win32" ? "python.exe" : "python3";
  const candidate = path.join(backendDir(), ".venv", venvDir, venvPython);
  try {
    require("fs").accessSync(candidate);
    return candidate;
  } catch {
    return process.platform === "win32" ? "python" : "python3";
  }
}

function startBackend() {
  const dir = backendDir();
  const python = resolvePython();
  backendProc = spawn(python, ["main.py"], {
    cwd: dir,
    env: { ...process.env, PYTHONUNBUFFERED: "1" },
  });
  backendProc.stdout.on("data", (d) => process.stdout.write(`[backend] ${d}`));
  backendProc.stderr.on("data", (d) => process.stderr.write(`[backend] ${d}`));
  backendProc.on("exit", (code) =>
    console.log(`[backend] exited with code ${code}`),
  );
}

function waitForBackend(retries = 40) {
  return new Promise((resolve) => {
    const attempt = (left) => {
      const req = http.get(
        { host: "127.0.0.1", port: BACKEND_PORT, path: "/" },
        (res) => {
          res.destroy();
          resolve(true);
        },
      );
      req.on("error", () => {
        if (left <= 0) return resolve(false);
        setTimeout(() => attempt(left - 1), 500);
      });
    };
    attempt(retries);
  });
}

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    backgroundColor: "#02040A",
    titleBarStyle: "hiddenInset",
    frame: process.platform === "darwin",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // Open external links in the user's browser, not inside the app.
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  if (isDev) {
    await mainWindow.loadURL("http://localhost:5173");
    mainWindow.webContents.openDevTools({ mode: "detach" });
  } else {
    await mainWindow.loadFile(path.join(__dirname, "..", "dist", "index.html"));
  }

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

app.whenReady().then(async () => {
  startBackend();
  await waitForBackend();
  await createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  if (backendProc && !backendProc.killed) {
    backendProc.kill("SIGTERM");
  }
});

// Window controls for the frameless chrome.
ipcMain.handle("window:minimize", () => mainWindow?.minimize());
ipcMain.handle("window:maximize", () =>
  mainWindow?.isMaximized() ? mainWindow.unmaximize() : mainWindow?.maximize(),
);
ipcMain.handle("window:close", () => mainWindow?.close());
