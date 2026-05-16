/**
 * electron/main.js — AUA-Veritas Electron main process.
 *
 * Responsibilities:
 *   - Start the Python FastAPI backend silently on app launch
 *   - Create the main browser window (loads React UI)
 *   - Manage system tray icon (app stays running in background)
 *   - Handle app lifecycle (startup, quit, reopen on mac dock click)
 *   - Provide IPC bridge between renderer and native OS features
 *
 * Backend: uvicorn api.main:app --port 47821
 * UI:      http://localhost:47822 (Vite dev) or ui/dist/index.html (production)
 */

const { app, BrowserWindow, Tray, Menu, ipcMain, nativeImage, shell } = require('electron')
const path = require('path')
const { spawn } = require('child_process')
const fs = require('fs')

// ── Constants ─────────────────────────────────────────────────────────────────

const API_PORT = 47821
const UI_PORT  = 47822
const IS_DEV   = process.env.NODE_ENV !== 'production' && !app.isPackaged

// ── State ─────────────────────────────────────────────────────────────────────

let mainWindow  = null
let tray        = null
let apiProcess  = null
let apiReady    = false

// ── Python backend ────────────────────────────────────────────────────────────

function startApiServer() {
  const resourcesPath = IS_DEV
    ? path.join(__dirname, '..')
    : process.resourcesPath

  let pythonCmd
  let apiArgs

  // Always prefer the built binary (works in both dev and production)
  const binaryName = process.platform === 'win32' ? 'veritas-backend.exe' : 'veritas-backend'
  const devBinary = path.join(resourcesPath, 'dist-backend', binaryName)

  if (IS_DEV && fs.existsSync(devBinary)) {
    // Dev with built binary — fastest, most reliable
    pythonCmd = devBinary
    apiArgs = []
    if (process.platform !== 'win32') {
      try { require('child_process').execSync(`chmod +x "${devBinary}"`) } catch (_) {}
    }
  } else if (IS_DEV) {
    // Dev fallback: try .venv first, then system python
    const venvPaths = [
      path.join(resourcesPath, '.venv', 'bin', 'python3'),
      path.join(resourcesPath, 'venv', 'bin', 'python3'),
    ]
    const venvPython = venvPaths.find(p => fs.existsSync(p))
    pythonCmd = venvPython || 'python3'
    apiArgs = [
      '-m', 'uvicorn', 'api.main:app',
      '--port', String(API_PORT),
      '--host', '127.0.0.1',
      '--no-access-log',
    ]
  } else {
    // Production: use bundled PyInstaller binary
    const binaryName = process.platform === 'win32' ? 'veritas-backend.exe' : 'veritas-backend'
    const bundledBinary = path.join(resourcesPath, 'backend', binaryName)
    if (fs.existsSync(bundledBinary)) {
      // Make executable on unix
      if (process.platform !== 'win32') {
        try { require('child_process').execSync(`chmod +x "${bundledBinary}"`) } catch (_) {}
      }
      pythonCmd = bundledBinary
      apiArgs = []
    } else {
      // Fallback to system python if binary not found (shouldn't happen in production)
      console.error('Backend binary not found at:', bundledBinary)
      pythonCmd = 'python3'
      apiArgs = ['-m', 'uvicorn', 'api.main:app', '--port', String(API_PORT), '--host', '127.0.0.1']
    }
  }

  const logDir = app.getPath('logs')
  if (!fs.existsSync(logDir)) fs.mkdirSync(logDir, { recursive: true })
  const logPath = path.join(logDir, 'api.log')
  const logStream = fs.createWriteStream(logPath, { flags: 'a' })

  console.log(`Starting API server: ${pythonCmd}`)

  apiProcess = spawn(pythonCmd, apiArgs, {
    cwd: IS_DEV ? path.join(__dirname, '..') : resourcesPath,
    env: {
      ...process.env,
      PYTHONPATH: IS_DEV ? path.join(__dirname, '..') : resourcesPath,
      VERITAS_API_PORT: String(API_PORT),
      VERITAS_API_HOST: '127.0.0.1',
    },
  })

  apiProcess.stdout.pipe(logStream)
  apiProcess.stderr.pipe(logStream)

  // Also write startup info to log
  logStream.write(`\n[${new Date().toISOString()}] Starting backend: ${pythonCmd}\n`)
  logStream.write(`[${new Date().toISOString()}] Args: ${JSON.stringify(apiArgs)}\n`)
  logStream.write(`[${new Date().toISOString()}] CWD: ${IS_DEV ? path.join(__dirname, '..') : resourcesPath}\n`)

  apiProcess.on('error', (err) => {
    console.error('API process error:', err)
  })

  apiProcess.on('exit', (code) => {
    console.log(`API process exited with code ${code}`)
    apiReady = false
  })

  // Poll until the API is ready
  const pollInterval = setInterval(async () => {
    try {
      const response = await fetch(`http://127.0.0.1:${API_PORT}/health`)
      if (response.ok) {
        apiReady = true
        clearInterval(pollInterval)
        console.log('API server ready')
        if (mainWindow) {
          mainWindow.webContents.send('api-ready')
        }
      }
    } catch (_) {
      // Not ready yet
    }
  }, 500)

  // Timeout after 30 seconds
  setTimeout(() => {
    if (!apiReady) {
      clearInterval(pollInterval)
      console.error('API server failed to start within 30 seconds')
    }
  }, 30000)
}

function stopApiServer() {
  if (apiProcess) {
    apiProcess.kill('SIGTERM')
    apiProcess = null
  }
}

// ── Main window ───────────────────────────────────────────────────────────────

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    backgroundColor: '#fafaf8',
    show: false,   // show after content loads
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  })

  // Load the UI
  // In dev: try ui/dist first (already built); only use Vite if VITE_DEV env var is set
  const distIndex = path.join(__dirname, '..', 'ui', 'dist', 'index.html')
  if (!IS_DEV || !app.isPackaged) {
    if (process.env.VITE_DEV === '1') {
      mainWindow.loadURL(`http://localhost:${UI_PORT}`)
    } else if (fs.existsSync(distIndex)) {
      mainWindow.loadFile(distIndex)
    } else {
      mainWindow.loadURL(`http://localhost:${UI_PORT}`)
    }
  } else {
    mainWindow.loadFile(distIndex)
  }

  mainWindow.once('ready-to-show', () => {
    mainWindow.show()
    // If API is already ready, notify renderer
    if (apiReady) {
      mainWindow.webContents.send('api-ready')
    }
  })

  mainWindow.on('close', (event) => {
    // On macOS, closing the window hides it (app stays in tray)
    if (process.platform === 'darwin' && !app.isQuitting) {
      event.preventDefault()
      mainWindow.hide()
    }
  })

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

// ── System tray ───────────────────────────────────────────────────────────────

function createTray() {
  // Use a simple template icon (works on all platforms)
  const iconPath = path.join(__dirname, '..', 'assets', 'tray-icon.png')
  const icon = fs.existsSync(iconPath)
    ? nativeImage.createFromPath(iconPath)
    : nativeImage.createEmpty()

  tray = new Tray(icon)
  tray.setToolTip('AUA-Veritas')

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Open AUA-Veritas',
      click: () => {
        if (mainWindow) {
          mainWindow.show()
          mainWindow.focus()
        } else {
          createMainWindow()
        }
      },
    },
    { type: 'separator' },
    {
      label: 'API Status',
      enabled: false,
      label: apiReady ? '● API running' : '○ API starting...',
    },
    { type: 'separator' },
    {
      label: 'Quit AUA-Veritas',
      click: () => {
        app.isQuitting = true
        app.quit()
      },
    },
  ])

  tray.setContextMenu(contextMenu)
  tray.on('click', () => {
    if (mainWindow) {
      if (mainWindow.isVisible()) {
        mainWindow.focus()
      } else {
        mainWindow.show()
        mainWindow.focus()
      }
    } else {
      createMainWindow()
    }
  })
}

// ── IPC handlers ──────────────────────────────────────────────────────────────

function setupIpc() {
  // Open external URLs in default browser (API key pages etc.)
  ipcMain.handle('open-external', async (_, url) => {
    await shell.openExternal(url)
  })

  // Get app version
  ipcMain.handle('get-version', () => app.getVersion())

  // Get API status
  ipcMain.handle('api-status', () => ({ ready: apiReady, port: API_PORT }))

  // Relay to API (avoids CORS issues in production build)
  ipcMain.handle('api-request', async (_, { method, path: apiPath, body }) => {
    try {
      const res = await fetch(`http://127.0.0.1:${API_PORT}${apiPath}`, {
        method: method || 'GET',
        headers: { 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
      })
      const data = await res.json()
      return { ok: res.ok, status: res.status, data }
    } catch (err) {
      return { ok: false, status: 0, error: err.message }
    }
  })

  // Minimize to tray
  ipcMain.handle('minimize-to-tray', () => {
    if (mainWindow) mainWindow.hide()
  })
}

// ── App lifecycle ─────────────────────────────────────────────────────────────

// Start backend immediately — before window is ready — so it can warm up
// in parallel with Electron initialising. Saves 1-2 seconds on cold start.
startApiServer()

app.whenReady().then(() => {
  setupIpc()
  createMainWindow()
  createTray()

  app.on('activate', () => {
    // On macOS, re-show the window when dock icon is clicked
    if (mainWindow === null) {
      createMainWindow()
    } else {
      mainWindow.show()
    }
  })
})

app.on('window-all-closed', () => {
  // On macOS, don't quit when all windows are closed
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('before-quit', () => {
  app.isQuitting = true
  stopApiServer()
})

// Prevent multiple instances
const gotLock = app.requestSingleInstanceLock()
if (!gotLock) {
  app.quit()
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore()
      mainWindow.show()
      mainWindow.focus()
    }
  })
}
