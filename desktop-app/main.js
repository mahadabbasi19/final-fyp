// =============================================================================
// main.js — Electron Main Process
// CodeNova IDE: VS Code-style Desktop Editor
// =============================================================================

const { app, BrowserWindow, Menu, ipcMain, dialog, shell } = require('electron');
const path = require('path');
const fs = require('fs');
const fsPromises = fs.promises;
const os = require('os');
const { spawn } = require('child_process');

app.disableHardwareAcceleration();

let mainWindow;
let pty;
let backendProcess = null;
const BACKEND_PORT = 8000;
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;
// Per-launch shared secret. The backend rejects any request that doesn't
// echo this in X-CodeNova-Token, so a malicious webpage in the user's
// browser cannot drive the local API (rename-symbol, git push, etc).
const BACKEND_AUTH_TOKEN = require('crypto').randomBytes(32).toString('hex');

try {
  pty = require('node-pty');
} catch (e) {
  console.warn('node-pty not available. Integrated terminal disabled.', e.message);
}

const terminals = new Map();
let nextTerminalId = 1;

// ---------------------------------------------------------------------------
// Java Auto-Detection
// ---------------------------------------------------------------------------

// Per-user config (shared with the backend) — used to remember a JDK the
// user located manually via the "Locate JDK" picker.
function userConfigPath() {
  return path.join(os.homedir(), '.codenova', 'config.json');
}
function readUserConfig() {
  try { return JSON.parse(fs.readFileSync(userConfigPath(), 'utf-8')); }
  catch { return {}; }
}
function writeUserConfig(patch) {
  const dir = path.join(os.homedir(), '.codenova');
  try { fs.mkdirSync(dir, { recursive: true }); } catch (_) {}
  const cfg = { ...readUserConfig(), ...patch };
  fs.writeFileSync(userConfigPath(), JSON.stringify(cfg, null, 2));
  return cfg;
}

// Validate that a folder is a real JDK (has the javac compiler, not just a JRE).
function isValidJdk(home) {
  if (!home) return false;
  const javacName = process.platform === 'win32' ? 'javac.exe' : 'javac';
  return fs.existsSync(path.join(home, 'bin', javacName));
}

// Detect whether a JRE (java runtime) exists even when no JDK does — lets us
// tell the user precisely "you have a runtime but need the JDK" instead of a
// vague "not found".
function hasJreOnly() {
  try {
    const cp = require('child_process');
    const r = cp.spawnSync('java', ['-version'], { encoding: 'utf-8', timeout: 3000 });
    return r.status === 0;
  } catch { return false; }
}

function findJavaHome() {
  const isWin = process.platform === 'win32';
  const isMac = process.platform === 'darwin';
  const javacName = isWin ? 'javac.exe' : 'javac';

  // 0. A JDK the user located manually (highest priority — they chose it).
  const savedJdk = readUserConfig().jdk_home;
  if (isValidJdk(savedJdk)) return savedJdk;

  // 1. Honour JAVA_HOME if it points at a usable JDK.
  if (process.env.JAVA_HOME && fs.existsSync(path.join(process.env.JAVA_HOME, 'bin', javacName))) {
    return process.env.JAVA_HOME;
  }

  // 2. macOS: ask /usr/libexec/java_home (canonical lookup).
  if (isMac) {
    try {
      const out = require('child_process')
        .execFileSync('/usr/libexec/java_home', { encoding: 'utf-8', timeout: 2000 })
        .trim();
      if (out && fs.existsSync(path.join(out, 'bin', 'javac'))) return out;
    } catch (_) {}
  }

  // 3. Platform-specific install roots.
  const searchDirs = isWin
    ? [
        'C:\\Program Files\\Java',
        'C:\\Program Files\\Microsoft',           // Microsoft OpenJDK
        'C:\\Program Files\\Eclipse Adoptium',    // Temurin
        'C:\\Program Files\\Eclipse Foundation',
        'C:\\Program Files\\Zulu',
        'C:\\Program Files\\Amazon Corretto',
        'C:\\Program Files\\BellSoft',            // Liberica
        'C:\\Program Files\\RedHat',
        'C:\\Program Files\\AdoptOpenJDK',
        'C:\\Program Files (x86)\\Java',
        'C:\\Program Files (x86)\\Eclipse Adoptium',
      ]
    : isMac
    ? [
        '/Library/Java/JavaVirtualMachines',
        '/opt/homebrew/opt',
        '/usr/local/opt',
      ]
    : [
        '/usr/lib/jvm',
        '/usr/java',
        '/opt/java',
      ];

  for (const dir of searchDirs) {
    if (!fs.existsSync(dir)) continue;
    try {
      const entries = fs.readdirSync(dir).sort().reverse(); // newest-looking first
      for (const entry of entries) {
        // On macOS the JDK lives under <name>/Contents/Home; check both.
        const candidates = [
          path.join(dir, entry),
          path.join(dir, entry, 'Contents', 'Home'),
          path.join(dir, entry, 'libexec', 'openjdk.jdk', 'Contents', 'Home'),
        ];
        for (const jHome of candidates) {
          if (fs.existsSync(path.join(jHome, 'bin', javacName))) return jHome;
        }
      }
    } catch (_) {}
  }

  // 4. Windows registry — the authoritative record of installed JDKs.
  if (isWin) {
    try {
      const cp = require('child_process');
      const keys = [
        'HKLM\\SOFTWARE\\JavaSoft\\JDK',
        'HKLM\\SOFTWARE\\JavaSoft\\Java Development Kit',
        'HKLM\\SOFTWARE\\WOW6432Node\\JavaSoft\\JDK',
      ];
      for (const key of keys) {
        const out = cp.spawnSync('reg', ['query', key, '/s', '/v', 'JavaHome'], { encoding: 'utf-8', timeout: 4000 });
        if (out.status === 0 && out.stdout) {
          const matches = [...out.stdout.matchAll(/JavaHome\s+REG_SZ\s+(.+)/g)].map(m => m[1].trim());
          for (const home of matches.reverse()) {  // newest last → try newest first
            if (isValidJdk(home)) return home;
          }
        }
      }
    } catch (_) {}
  }

  // 5. Last resort: `where javac` (Windows) / `which javac` (Unix). On macOS
  // /usr/bin/javac is a STUB even without a JDK, so verify it actually runs.
  try {
    const cp = require('child_process');
    const finder = isWin ? 'where' : 'which';
    const out = cp.spawnSync(finder, ['javac'], { encoding: 'utf-8', timeout: 2000 });
    if (out.status === 0 && out.stdout) {
      const first = out.stdout.split(/\r?\n/).find(Boolean);
      if (first) {
        const check = cp.spawnSync(first.trim(), ['-version'], { encoding: 'utf-8', timeout: 3000 });
        if (check.status === 0) return path.dirname(path.dirname(first.trim()));
      }
    }
  } catch (_) {}

  return null;
}

// Apply a JDK home to this process's environment so BOTH the Python backend
// and every integrated terminal (spawned with env: process.env) can run javac.
function applyJavaHome(home) {
  if (!home) return;
  const javaBin = path.join(home, 'bin');
  const pathSep = process.platform === 'win32' ? ';' : ':';
  if (!(process.env.PATH || '').split(pathSep).includes(javaBin)) {
    process.env.PATH = javaBin + pathSep + (process.env.PATH || '');
  }
  process.env.JAVA_HOME = home;
}

let JAVA_HOME = findJavaHome();
if (JAVA_HOME) {
  applyJavaHome(JAVA_HOME);
  console.log('JDK detected:', JAVA_HOME);
} else {
  console.warn('JDK not found. Java compile/run disabled until a JDK is located.');
}

// Let the renderer query / re-detect / manually locate the JDK.
ipcMain.handle('java:status', () => ({
  found: !!JAVA_HOME,
  home: JAVA_HOME || null,
  jreOnly: !JAVA_HOME && hasJreOnly(),
}));

ipcMain.handle('java:redetect', () => {
  JAVA_HOME = findJavaHome();
  if (JAVA_HOME) applyJavaHome(JAVA_HOME);
  return { found: !!JAVA_HOME, home: JAVA_HOME || null, jreOnly: !JAVA_HOME && hasJreOnly() };
});

// Folder picker: user points at their JDK; we validate, persist, and apply it
// live (no restart) so new terminals and the backend pick it up.
ipcMain.handle('java:locate', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: 'Select your JDK folder (the one containing bin\\javac)',
    properties: ['openDirectory'],
    message: 'Choose the JDK installation folder, e.g. C:\\Program Files\\Java\\jdk-21',
  });
  if (result.canceled || !result.filePaths.length) return { canceled: true };
  let chosen = result.filePaths[0];
  // Be forgiving: accept the bin folder or a parent that contains the JDK.
  const candidates = [chosen, path.dirname(chosen), path.join(chosen, '..')];
  const valid = candidates.find(isValidJdk);
  if (!valid) {
    return { canceled: false, error: 'That folder does not contain bin/javac. Pick the JDK root folder (e.g. jdk-21), not the JRE.' };
  }
  writeUserConfig({ jdk_home: valid });
  JAVA_HOME = valid;
  applyJavaHome(valid);
  return { canceled: false, found: true, home: valid };
});

// ---------------------------------------------------------------------------
// Python Backend Process Management
// ---------------------------------------------------------------------------
function getBackendDir() {
  // In dev: sibling folder; in production: bundled
  const devPath = path.join(__dirname, '..', 'java_refactoring_engine');
  if (fs.existsSync(devPath)) return devPath;
  return path.join(process.resourcesPath, 'java_refactoring_engine');
}

function getBundledBackendBinary() {
  // Standalone PyInstaller binary — end users need NO Python installed.
  // Checked first in production, then in dev (if the developer built it).
  const name = process.platform === 'win32' ? 'codenova-backend.exe' : 'codenova-backend';
  const candidates = [
    path.join(process.resourcesPath || '', 'backend-bin', name),
    path.join(__dirname, '..', 'java_refactoring_engine', 'dist', name),
  ];
  for (const p of candidates) {
    try { if (fs.existsSync(p)) return p; } catch (_) {}
  }
  return null;
}

function killPortProcess(port) {
  return new Promise((resolve) => {
    if (process.platform === 'win32') {
      const find = spawn('cmd', ['/c', `for /f "tokens=5" %a in ('netstat -ano ^| findstr :${port} ^| findstr LISTENING') do taskkill /PID %a /F`], { shell: true });
      find.on('close', () => resolve());
      setTimeout(() => resolve(), 3000);
    } else {
      const find = spawn('sh', ['-c', `lsof -ti:${port} | xargs kill -9 2>/dev/null`]);
      find.on('close', () => resolve());
      setTimeout(() => resolve(), 3000);
    }
  });
}

function startBackend() {
  return new Promise(async (resolve) => {
    // Kill any stale process on our port first
    await killPortProcess(BACKEND_PORT);

    // Preferred: standalone PyInstaller binary — works with no Python
    // installed, exactly like VS Code's bundled runtime model.
    const bundledBinary = getBundledBackendBinary();

    if (bundledBinary) {
      console.log('Starting bundled backend binary:', bundledBinary);
      backendProcess = spawn(bundledBinary, [], {
        cwd: path.dirname(bundledBinary),
        env: {
          ...process.env,
          CODENOVA_BACKEND_PORT: String(BACKEND_PORT),
          CODENOVA_AUTH_TOKEN: BACKEND_AUTH_TOKEN,
        },
        stdio: ['pipe', 'pipe', 'pipe']
      });
    } else {
      // Fallback: source + system Python (development machines).
      const backendDir = getBackendDir();
      const mainPy = path.join(backendDir, 'main.py');

      if (!fs.existsSync(mainPy)) {
        console.warn('Backend main.py not found at:', mainPy);
        resolve(false);
        return;
      }

      console.log('Starting FastAPI backend from source:', backendDir);
      const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';

      backendProcess = spawn(pythonCmd, [
        '-m', 'uvicorn', 'main:app',
        '--host', '127.0.0.1',
        '--port', String(BACKEND_PORT),
        '--log-level', 'info'
      ], {
        cwd: backendDir,
        env: {
          ...process.env,
          PYTHONUNBUFFERED: '1',
          CODENOVA_AUTH_TOKEN: BACKEND_AUTH_TOKEN,
        },
        stdio: ['pipe', 'pipe', 'pipe']
      });
    }

    let started = false;

    backendProcess.stdout.on('data', (data) => {
      const msg = data.toString();
      console.log('[Backend]', msg.trim());
      if (!started && msg.includes('Uvicorn running')) {
        started = true;
        resolve(true);
      }
    });

    backendProcess.stderr.on('data', (data) => {
      const msg = data.toString();
      console.log('[Backend]', msg.trim());
      if (!started && msg.includes('Uvicorn running')) {
        started = true;
        resolve(true);
      }
    });

    backendProcess.on('error', (err) => {
      console.error('Backend process error:', err.message);
      backendProcess = null;
      if (!started) resolve(false);
    });

    backendProcess.on('exit', (code) => {
      console.log('Backend process exited with code:', code);
      backendProcess = null;
      if (!started) resolve(false);
    });

    // Timeout — resolve false if backend doesn't start in 15s
    setTimeout(() => {
      if (!started) {
        console.warn('Backend startup timed out');
        resolve(false);
      }
    }, 15000);
  });
}

function stopBackend() {
  if (backendProcess) {
    try {
      if (process.platform === 'win32') {
        spawn('taskkill', ['/pid', String(backendProcess.pid), '/f', '/t']);
      } else {
        backendProcess.kill('SIGTERM');
      }
    } catch (_) {}
    backendProcess = null;
  }
}

// ---------------------------------------------------------------------------
// Window Creation
// ---------------------------------------------------------------------------
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 800,
    minHeight: 600,
    title: 'CodeNova IDE',
    backgroundColor: '#1e1e1e',
    frame: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: false
    },
    icon: path.join(__dirname, 'assets', 'icon.png')
  });

  mainWindow.loadFile('index.html');

  if (process.argv.includes('--dev')) {
    mainWindow.webContents.openDevTools();
  }

  mainWindow.on('closed', () => {
    terminals.forEach((term) => { try { term.kill(); } catch (_) {} });
    terminals.clear();
    mainWindow = null;
  });
}

// ---------------------------------------------------------------------------
// Application Menu (VS Code-style)
// ---------------------------------------------------------------------------
function buildAppMenu() {
  const isMac = process.platform === 'darwin';
  const template = [
    // macOS requires the first menu to be the application menu — it owns
    // Cmd+Q (Quit), Cmd+H (Hide), About, etc. Without it none of those
    // system shortcuts work.
    ...(isMac ? [{
      label: 'CodeNova IDE',
      submenu: [
        { role: 'about' },
        { type: 'separator' },
        { role: 'services' },
        { type: 'separator' },
        { role: 'hide' },
        { role: 'hideOthers' },
        { role: 'unhide' },
        { type: 'separator' },
        { role: 'quit' }
      ]
    }] : []),
    {
      label: 'File',
      submenu: [
        { label: 'New File', accelerator: 'CmdOrCtrl+N', click: () => mainWindow?.webContents.send('menu:newFile') },
        { label: 'New Window', accelerator: 'CmdOrCtrl+Shift+N', click: () => createWindow() },
        { type: 'separator' },
        { label: 'Open File...', accelerator: 'CmdOrCtrl+O', click: () => mainWindow?.webContents.send('menu:openFile') },
        { label: 'Open Folder...', accelerator: 'CmdOrCtrl+K CmdOrCtrl+O', click: () => mainWindow?.webContents.send('menu:openFolder') },
        { type: 'separator' },
        { label: 'Save', accelerator: 'CmdOrCtrl+S', click: () => mainWindow?.webContents.send('menu:save') },
        { label: 'Save As...', accelerator: 'CmdOrCtrl+Shift+S', click: () => mainWindow?.webContents.send('menu:saveAs') },
        { type: 'separator' },
        { label: 'Auto Save', type: 'checkbox', checked: false, click: (mi) => mainWindow?.webContents.send('menu:autoSave', mi.checked) },
        { type: 'separator' },
        isMac ? { role: 'close' } : { label: 'Exit', accelerator: 'Alt+F4', click: () => app.quit() }
      ]
    },
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' }, { role: 'redo' }, { type: 'separator' },
        { role: 'cut' }, { role: 'copy' }, { role: 'paste' }, { type: 'separator' },
        { label: 'Find', accelerator: 'CmdOrCtrl+F', click: () => mainWindow?.webContents.send('menu:find') },
        { label: 'Replace', accelerator: 'CmdOrCtrl+H', click: () => mainWindow?.webContents.send('menu:replace') }
      ]
    },
    {
      label: 'Selection',
      submenu: [
        { role: 'selectAll' },
        { type: 'separator' },
        { label: 'Expand Selection', accelerator: 'Shift+Alt+Right', click: () => mainWindow?.webContents.send('menu:expandSelection') },
        { label: 'Shrink Selection', accelerator: 'Shift+Alt+Left', click: () => mainWindow?.webContents.send('menu:shrinkSelection') }
      ]
    },
    {
      label: 'View',
      submenu: [
        { label: 'Explorer', accelerator: 'CmdOrCtrl+Shift+E', click: () => mainWindow?.webContents.send('menu:toggleExplorer') },
        { label: 'Search', accelerator: 'CmdOrCtrl+Shift+F', click: () => mainWindow?.webContents.send('menu:toggleSearch') },
        { type: 'separator' },
        { label: 'Terminal', accelerator: 'CmdOrCtrl+`', click: () => mainWindow?.webContents.send('menu:toggleTerminal') },
        { label: 'Output', accelerator: 'CmdOrCtrl+Shift+U', click: () => mainWindow?.webContents.send('menu:toggleOutput') },
        { type: 'separator' },
        { role: 'resetZoom' }, { role: 'zoomIn' }, { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' }
      ]
    },
    {
      label: 'Run',
      submenu: [
        { label: 'Run File', accelerator: 'F5', click: () => mainWindow?.webContents.send('menu:runFile') },
        { label: 'Stop', accelerator: 'Shift+F5', click: () => mainWindow?.webContents.send('menu:stopRun') }
      ]
    },
    {
      label: 'Terminal',
      submenu: [
        { label: 'New Terminal', accelerator: 'CmdOrCtrl+Shift+`', click: () => mainWindow?.webContents.send('menu:newTerminal') }
      ]
    },
    // Window menu: Cmd+M minimize, Cmd+W close, zoom, etc.
    ...(isMac ? [{ role: 'windowMenu' }] : []),
    {
      label: 'Help',
      submenu: [
        { label: 'About CodeNova IDE', click: () => {
          const iconPath = path.join(__dirname, 'assets', 'icon.png');
          const opts = { type: 'info', title: 'About CodeNova IDE', message: 'CodeNova IDE v2.0.0', detail: 'A VS Code-style Desktop Editor built with Electron and Monaco Editor.\nPowered by Java Refactoring Engine.' };
          if (fs.existsSync(iconPath)) { const { nativeImage } = require('electron'); opts.icon = nativeImage.createFromPath(iconPath); }
          dialog.showMessageBox(mainWindow, opts);
        }},
        { type: 'separator' },
        { role: 'toggleDevTools' }
      ]
    }
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

// ---------------------------------------------------------------------------
// IPC Handlers — File System
// ---------------------------------------------------------------------------
ipcMain.handle('dialog:openFolder', async () => {
  const result = await dialog.showOpenDialog(mainWindow, { properties: ['openDirectory'] });
  if (!result.canceled && result.filePaths.length > 0) {
    return { canceled: false, path: result.filePaths[0] };
  }
  return { canceled: true };
});

ipcMain.handle('dialog:openFile', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openFile'],
    filters: [
      { name: 'All Files', extensions: ['*'] },
      { name: 'JavaScript', extensions: ['js', 'jsx', 'ts', 'tsx'] },
      { name: 'Python', extensions: ['py'] },
      { name: 'Java', extensions: ['java'] },
      { name: 'Web', extensions: ['html', 'css', 'json'] }
    ]
  });
  if (!result.canceled && result.filePaths.length > 0) {
    const content = await fsPromises.readFile(result.filePaths[0], 'utf-8');
    return { canceled: false, path: result.filePaths[0], content };
  }
  return { canceled: true };
});

ipcMain.handle('dialog:saveAs', async (event, { defaultPath }) => {
  const result = await dialog.showSaveDialog(mainWindow, {
    defaultPath: defaultPath || 'untitled',
    filters: [{ name: 'All Files', extensions: ['*'] }]
  });
  if (!result.canceled) return { canceled: false, path: result.filePath };
  return { canceled: true };
});

ipcMain.handle('fs:readDir', async (event, dirPath) => {
  const entries = await fsPromises.readdir(dirPath, { withFileTypes: true });
  return entries
    .filter(e => !e.name.startsWith('.'))
    .map(entry => ({
      name: entry.name,
      path: path.join(dirPath, entry.name),
      isDirectory: entry.isDirectory(),
      isFile: entry.isFile()
    }))
    .sort((a, b) => {
      if (a.isDirectory && !b.isDirectory) return -1;
      if (!a.isDirectory && b.isDirectory) return 1;
      return a.name.localeCompare(b.name);
    });
});

ipcMain.handle('fs:readFile', async (event, filePath) => {
  return await fsPromises.readFile(filePath, 'utf-8');
});

ipcMain.handle('fs:writeFile', async (event, filePath, content) => {
  await fsPromises.writeFile(filePath, content, 'utf-8');
  return true;
});

ipcMain.handle('fs:createFile', async (event, filePath) => {
  try {
    await fsPromises.access(filePath);
    throw new Error(`File already exists: ${path.basename(filePath)}`);
  } catch (e) {
    if (e.message.startsWith('File already exists')) throw e;
  }
  await fsPromises.writeFile(filePath, '', 'utf-8');
  return true;
});

ipcMain.handle('fs:createDir', async (event, dirPath) => {
  try {
    await fsPromises.access(dirPath);
    throw new Error(`Folder already exists: ${path.basename(dirPath)}`);
  } catch (e) {
    if (e.message.startsWith('Folder already exists')) throw e;
  }
  await fsPromises.mkdir(dirPath, { recursive: true });
  return true;
});

ipcMain.handle('fs:delete', async (event, targetPath) => {
  const stat = await fsPromises.stat(targetPath);
  if (stat.isDirectory()) {
    await fsPromises.rm(targetPath, { recursive: true, force: true });
  } else {
    await fsPromises.unlink(targetPath);
  }
  return true;
});

ipcMain.handle('fs:rename', async (event, oldPath, newPath) => {
  await fsPromises.rename(oldPath, newPath);
  return true;
});

ipcMain.handle('fs:stat', async (event, targetPath) => {
  try {
    const stat = await fsPromises.stat(targetPath);
    return { isFile: stat.isFile(), isDirectory: stat.isDirectory(), size: stat.size, modified: stat.mtimeMs };
  } catch { return null; }
});

// ---------------------------------------------------------------------------
// IPC Handlers — Terminal (node-pty)
// ---------------------------------------------------------------------------
ipcMain.handle('terminal:create', (event, { cols, rows, cwd }) => {
  if (!pty) throw new Error('node-pty is not available.');
  const shellPath = getDefaultShell();
  const id = nextTerminalId++;
  const term = pty.spawn(shellPath, getShellArgs(shellPath), {
    name: 'xterm-256color',
    cols: cols || 80,
    rows: rows || 24,
    cwd: cwd || os.homedir(),
    env: process.env
  });
  term.onData((data) => {
    if (mainWindow && !mainWindow.isDestroyed()) mainWindow.webContents.send('terminal:data', { id, data });
  });
  term.onExit(({ exitCode }) => {
    terminals.delete(id);
    if (mainWindow && !mainWindow.isDestroyed()) mainWindow.webContents.send('terminal:exit', { id, exitCode });
  });
  terminals.set(id, term);
  return id;
});

ipcMain.on('terminal:write', (event, { id, data }) => {
  const term = terminals.get(id);
  if (term) term.write(data);
});

ipcMain.on('terminal:resize', (event, { id, cols, rows }) => {
  const term = terminals.get(id);
  if (term) { try { term.resize(cols, rows); } catch (_) {} }
});

ipcMain.on('terminal:kill', (event, { id }) => {
  const term = terminals.get(id);
  if (term) { term.kill(); terminals.delete(id); }
});

// ---------------------------------------------------------------------------
// IPC Handlers — Run / Execute File
// ---------------------------------------------------------------------------
ipcMain.handle('run:file', async (event, { filePath, cwd }) => {
  // The command strings below are interpolated into a shell (PowerShell on
  // Windows). A filename like `x"; rm -rf ~; "` would execute. Escaping
  // PowerShell quoting correctly is a losing game — reject instead.
  if (/["'`$;|&<>\n\r]/.test(filePath)) {
    throw new Error('File path contains characters that cannot be run safely (quotes, $, ;, |, &). Rename the file and try again.');
  }
  const ext = path.extname(filePath).toLowerCase();
  const commands = {
    '.py': `python "${filePath}"`,
    '.js': `node "${filePath}"`,
    '.ts': `npx ts-node "${filePath}"`,
    '.rb': `ruby "${filePath}"`,
    '.go': `go run "${filePath}"`,
    '.sh': `bash "${filePath}"`,
    '.ps1': `powershell -File "${filePath}"`,
  };
  if (ext === '.java') {
    const cn = path.basename(filePath, '.java');
    const dir = path.dirname(filePath);
    if (JAVA_HOME) {
      const javacPath = path.join(JAVA_HOME, 'bin', 'javac');
      const javaPath = path.join(JAVA_HOME, 'bin', 'java');
      return { command: `cd "${dir}"; & "${javacPath}" "${path.basename(filePath)}"; if ($?) { & "${javaPath}" ${cn} }` };
    }
    return { command: `cd "${dir}"; javac "${path.basename(filePath)}"; if ($?) { java ${cn} }` };
  }
  if (ext === '.cpp' || ext === '.cc') return { command: `g++ "${filePath}" -o "${filePath}.exe"; if ($?) { & "${filePath}.exe" }` };
  if (ext === '.c') return { command: `gcc "${filePath}" -o "${filePath}.exe"; if ($?) { & "${filePath}.exe" }` };
  if (commands[ext]) return { command: commands[ext] };
  throw new Error(`No run configuration for: ${ext}`);
});

// ---------------------------------------------------------------------------
// IPC Handlers — Workspace Search
// ---------------------------------------------------------------------------
ipcMain.handle('workspace:search', async (event, { rootPath, query }) => {
  const results = [];
  if (!rootPath || !query) return results;
  const maxResults = 200;
  const searchRegex = new RegExp(query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
  
  async function walkDir(dir, depth) {
    if (depth > 8 || results.length >= maxResults) return;
    try {
      const entries = await fs.promises.readdir(dir, { withFileTypes: true });
      for (const entry of entries) {
        if (results.length >= maxResults) break;
        const fullPath = path.join(dir, entry.name);
        if (entry.name.startsWith('.') || entry.name === 'node_modules' || entry.name === 'dist' || entry.name === '__pycache__') continue;
        if (entry.isDirectory()) {
          await walkDir(fullPath, depth + 1);
        } else if (entry.isFile()) {
          const ext = path.extname(entry.name).toLowerCase();
          const textExts = ['.java','.py','.js','.ts','.html','.css','.json','.md','.txt','.xml','.yaml','.yml','.sh','.bat','.ps1','.c','.cpp','.h','.go','.rb','.rs'];
          if (!textExts.includes(ext)) continue;
          try {
            const content = await fs.promises.readFile(fullPath, 'utf-8');
            const lines = content.split('\n');
            for (let i = 0; i < lines.length; i++) {
              if (results.length >= maxResults) break;
              if (searchRegex.test(lines[i])) {
                searchRegex.lastIndex = 0;
                results.push({
                  filePath: fullPath,
                  relativePath: path.relative(rootPath, fullPath),
                  line: i + 1,
                  content: lines[i].trim().substring(0, 200),
                });
              }
            }
          } catch (_) {}
        }
      }
    } catch (_) {}
  }
  await walkDir(rootPath, 0);
  return results;
});

// ---------------------------------------------------------------------------
// IPC Handlers — Misc
// ---------------------------------------------------------------------------
ipcMain.handle('app:getPath', (event, name) => app.getPath(name));
ipcMain.handle('path:sep', () => path.sep);
ipcMain.handle('path:basename', (event, p) => path.basename(p));
ipcMain.handle('path:dirname', (event, p) => path.dirname(p));
ipcMain.handle('path:join', (event, ...parts) => path.join(...parts));
ipcMain.handle('path:extname', (event, p) => path.extname(p));
ipcMain.handle('shell:openExternal', async (event, url) => { await shell.openExternal(url); });

// ---------------------------------------------------------------------------
// IPC Handlers — Backend API Proxy
// ---------------------------------------------------------------------------
async function backendFetch(endpoint, method, body) {
  const http = require('http');
  return new Promise((resolve, reject) => {
    const postData = body ? JSON.stringify(body) : null;
    const options = {
      hostname: '127.0.0.1',
      port: BACKEND_PORT,
      path: endpoint,
      method: method,
      headers: {
        'Content-Type': 'application/json',
        'X-CodeNova-Token': BACKEND_AUTH_TOKEN,
        ...(postData ? { 'Content-Length': Buffer.byteLength(postData) } : {})
      },
      timeout: 30000
    };
    const req = http.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try { resolve(JSON.parse(data)); }
        catch { resolve(data); }
      });
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('Backend request timed out')); });
    if (postData) req.write(postData);
    req.end();
  });
}

ipcMain.handle('backend:health', async () => {
  try {
    return await backendFetch('/health', 'GET');
  } catch (e) {
    return { status: 'unavailable', error: e.message };
  }
});

ipcMain.handle('backend:refactor', async (event, { java_code, apply_all, selected_refactorings }) => {
  return await backendFetch('/refactor', 'POST', { java_code, apply_all, selected_refactorings });
});

ipcMain.handle('backend:analyze', async (event, { java_code }) => {
  return await backendFetch('/analyze', 'POST', { java_code });
});

ipcMain.handle('backend:checkErrors', async (event, { java_code, project_root }) => {
  return await backendFetch('/check-errors', 'POST', { java_code, project_root });
});

ipcMain.handle('backend:stats', async () => {
  return await backendFetch('/stats', 'GET');
});

ipcMain.handle('backend:dependencyGraph', async (event, { java_code }) => {
  return await backendFetch('/dependency-graph', 'POST', { java_code });
});

ipcMain.handle('backend:refactorReview', async (event, { java_code, selected_refactorings }) => {
  return await backendFetch('/refactor/review', 'POST', { java_code, selected_refactorings });
});

ipcMain.handle('backend:refactorDecision', async (event, { session_id, action }) => {
  return await backendFetch('/refactor/decision', 'POST', { session_id, action });
});

ipcMain.handle('backend:chat', async (event, { user_message, code, file_path }) => {
  return await backendFetch('/chat', 'POST', { user_message, code, file_path });
});

ipcMain.handle('backend:chatHealthDashboard', async (event, { java_code }) => {
  return await backendFetch('/chat/health-dashboard', 'POST', { java_code });
});

// ---- Per-user OpenAI key management ----
ipcMain.handle('backend:openaiKeyStatus', async () => {
  return await backendFetch('/config/openai-key/status', 'GET');
});
ipcMain.handle('backend:openaiKeySet', async (event, { openai_api_key }) => {
  return await backendFetch('/config/openai-key', 'POST', { openai_api_key });
});
ipcMain.handle('backend:openaiKeyClear', async () => {
  return await backendFetch('/config/openai-key', 'DELETE');
});

// ---------------------------------------------------------------------------
// Git Backend IPC Handlers
// ---------------------------------------------------------------------------
ipcMain.handle('backend:gitStatus', async (event, { repo_path }) => {
  return await backendFetch('/git/status', 'POST', { repo_path });
});
ipcMain.handle('backend:gitInit', async (event, { repo_path }) => {
  return await backendFetch('/git/init', 'POST', { path: repo_path });
});
ipcMain.handle('backend:gitStage', async (event, { repo_path, paths }) => {
  return await backendFetch('/git/stage', 'POST', { repo_path, paths });
});
ipcMain.handle('backend:gitStageAll', async (event, { repo_path }) => {
  return await backendFetch('/git/stage-all', 'POST', { repo_path });
});
ipcMain.handle('backend:gitUnstage', async (event, { repo_path, paths }) => {
  return await backendFetch('/git/unstage', 'POST', { repo_path, paths });
});
ipcMain.handle('backend:gitDiscard', async (event, { repo_path, paths }) => {
  return await backendFetch('/git/discard', 'POST', { repo_path, paths });
});
ipcMain.handle('backend:gitCommit', async (event, { repo_path, message, author }) => {
  return await backendFetch('/git/commit', 'POST', { repo_path, message, author });
});
ipcMain.handle('backend:gitBranches', async (event, { repo_path }) => {
  return await backendFetch('/git/branches', 'POST', { repo_path });
});
ipcMain.handle('backend:gitBranchCreate', async (event, { repo_path, name, checkout }) => {
  return await backendFetch('/git/branch/create', 'POST', { repo_path, name, checkout });
});
ipcMain.handle('backend:gitBranchSwitch', async (event, { repo_path, name }) => {
  return await backendFetch('/git/branch/switch', 'POST', { repo_path, name });
});
ipcMain.handle('backend:gitBranchDelete', async (event, { repo_path, name, force }) => {
  return await backendFetch('/git/branch/delete', 'POST', { repo_path, name, force });
});
ipcMain.handle('backend:gitPush', async (event, { repo_path, remote, branch, set_upstream }) => {
  return await backendFetch('/git/push', 'POST', { repo_path, remote, branch, set_upstream });
});
ipcMain.handle('backend:gitPull', async (event, { repo_path, remote }) => {
  return await backendFetch('/git/pull', 'POST', { repo_path, remote });
});
ipcMain.handle('backend:gitFetch', async (event, { repo_path, remote }) => {
  return await backendFetch('/git/fetch', 'POST', { repo_path, remote });
});
ipcMain.handle('backend:gitDiff', async (event, { repo_path, path, staged }) => {
  return await backendFetch('/git/diff', 'POST', { repo_path, path, staged });
});
ipcMain.handle('backend:gitLog', async (event, { repo_path, max_count, file_path }) => {
  return await backendFetch('/git/log', 'POST', { repo_path, max_count, file_path });
});
ipcMain.handle('backend:gitStashSave', async (event, { repo_path, message }) => {
  return await backendFetch('/git/stash/save', 'POST', { repo_path, message });
});
ipcMain.handle('backend:gitStashPop', async (event, { repo_path }) => {
  return await backendFetch('/git/stash/pop', 'POST', { repo_path });
});
ipcMain.handle('backend:gitStashList', async (event, { repo_path }) => {
  return await backendFetch('/git/stash/list', 'POST', { repo_path });
});

// ---------------------------------------------------------------------------
// Embedded Collaboration Host — the app itself hosts the live session
// ---------------------------------------------------------------------------
const collabHost = require('./collab-host');

ipcMain.handle('collab:hostStart', async () => {
  try {
    return await collabHost.startHost();
  } catch (e) {
    return { error: e.message };
  }
});
ipcMain.handle('collab:hostStop', () => collabHost.stopHost());
ipcMain.handle('collab:hostInfo', () => collabHost.hostInfo());

app.on('before-quit', () => { try { collabHost.stopHost(); } catch (_) {} });

// ---------------------------------------------------------------------------
// GitHub OAuth Device Flow — "Sign in with GitHub" (like VS Code)
// ---------------------------------------------------------------------------
// Requires a (free) GitHub OAuth App with Device Flow enabled:
//   github.com/settings/developers → New OAuth App → any callback URL →
//   tick "Enable Device Flow" → copy the Client ID below.
// The client ID is public by design (no secret is used in device flow).
const GITHUB_CLIENT_ID = process.env.GITHUB_CLIENT_ID || 'REPLACE_WITH_OAUTH_APP_CLIENT_ID';

ipcMain.handle('github:deviceStart', async (event, opts) => {
  // Runtime override (set from the app's Settings menu) beats the constant,
  // so a shipped build can be activated without rebuilding.
  const clientId = (opts && opts.clientId) || GITHUB_CLIENT_ID;
  if (!clientId || clientId.startsWith('REPLACE_')) {
    return { error: 'GitHub OAuth not configured. Settings (gear icon) → "Set GitHub OAuth Client ID", or ask the app publisher to bake one in.' };
  }
  const res = await fetch('https://github.com/login/device/code', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ client_id: clientId, scope: 'repo' }),
  });
  if (!res.ok) return { error: `GitHub returned ${res.status}` };
  const data = await res.json();
  data._client_id = clientId;
  return data;
});

ipcMain.handle('github:deviceWait', async (event, { device_code, interval, clientId }) => {
  const pollMs = Math.max(5, interval || 5) * 1000;
  const deadline = Date.now() + 10 * 60 * 1000; // give the user 10 minutes
  while (Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, pollMs));
    const res = await fetch('https://github.com/login/oauth/access_token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({
        client_id: clientId || GITHUB_CLIENT_ID,
        device_code,
        grant_type: 'urn:ietf:params:oauth:grant-type:device_code',
      }),
    });
    const data = await res.json();
    if (data.access_token) {
      // Fetch the username so the UI can show who is signed in.
      let login = '';
      try {
        const who = await fetch('https://api.github.com/user', {
          headers: { Authorization: `Bearer ${data.access_token}`, Accept: 'application/vnd.github+json' },
        });
        if (who.ok) login = (await who.json()).login || '';
      } catch (_) {}
      return { token: data.access_token, login };
    }
    if (data.error === 'authorization_pending') continue;
    if (data.error === 'slow_down') { await new Promise((r) => setTimeout(r, 5000)); continue; }
    return { error: data.error_description || data.error || 'Authorization failed' };
  }
  return { error: 'Timed out waiting for GitHub authorization.' };
});

// ---------------------------------------------------------------------------
// Push to GitHub — Standalone Python subprocess
// ---------------------------------------------------------------------------
ipcMain.handle('push-to-github', async (event, { projectPath, repoUrl, commitMessage, token, githubLogin }) => {
  return new Promise((resolve) => {
    const scriptPath = path.join(__dirname, 'backend', 'github_push.py');

    if (!fs.existsSync(scriptPath)) {
      resolve({ success: false, error: 'github_push.py not found at: ' + scriptPath });
      return;
    }

    const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
    const args = JSON.stringify({
      project_path: projectPath,
      repo_url: repoUrl || '',
      commit_message: commitMessage || '',
      token: token || '',
      github_login: githubLogin || '',
    });

    const child = spawn(pythonCmd, [scriptPath, args], {
      cwd: projectPath,
      env: { ...process.env },
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    let stdout = '';
    let stderr = '';

    child.stdout.on('data', (data) => { stdout += data.toString(); });
    child.stderr.on('data', (data) => { stderr += data.toString(); });

    child.on('error', (err) => {
      resolve({ success: false, error: 'Failed to spawn Python: ' + err.message });
    });

    child.on('close', (code) => {
      if (code === 0 && stdout.trim()) {
        try {
          resolve(JSON.parse(stdout.trim()));
        } catch {
          resolve({ success: true, message: stdout.trim() });
        }
      } else {
        // Try to extract JSON error from stderr
        let errMsg = stderr.trim() || stdout.trim() || 'Unknown error (exit code ' + code + ')';
        try {
          const parsed = JSON.parse(errMsg);
          errMsg = parsed.error || errMsg;
        } catch { /* use raw string */ }
        resolve({ success: false, error: errMsg });
      }
    });
  });
});

// ---------------------------------------------------------------------------
// Multi-file Dependency Graph, Refactoring History, Rename Symbol
// ---------------------------------------------------------------------------
ipcMain.handle('backend:multiFileDependencyGraph', async (event, { files }) => {
  return await backendFetch('/dependency-graph/multi', 'POST', { files });
});

ipcMain.handle('backend:getRefactoringHistory', async () => {
  return await backendFetch('/refactoring/history', 'GET');
});

ipcMain.handle('backend:saveRefactoringHistory', async (event, entry) => {
  return await backendFetch('/refactoring/history', 'POST', entry);
});

ipcMain.handle('backend:clearRefactoringHistory', async () => {
  return await backendFetch('/refactoring/history', 'DELETE');
});

ipcMain.handle('backend:renameSymbol', async (event, { root_path, old_name, new_name }) => {
  return await backendFetch('/rename-symbol', 'POST', { root_path, old_name, new_name });
});

// ---------------------------------------------------------------------------
// Read all Java files in a directory (for dependency graph)
// ---------------------------------------------------------------------------
ipcMain.handle('fs:readJavaFiles', async (event, rootPath) => {
  const files = {};
  async function walk(dir) {
    try {
      const entries = await fsPromises.readdir(dir, { withFileTypes: true });
      for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);
        if (entry.isDirectory() && !entry.name.startsWith('.') && entry.name !== 'node_modules') {
          await walk(fullPath);
        } else if (entry.isFile() && entry.name.endsWith('.java')) {
          try {
            const code = await fsPromises.readFile(fullPath, 'utf-8');
            const relPath = path.relative(rootPath, fullPath).replace(/\\/g, '/');
            files[relPath] = code;
          } catch (_) {}
        }
      }
    } catch (_) {}
  }
  await walk(rootPath);
  return files;
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function getDefaultShell() {
  if (process.platform === 'win32') return 'powershell.exe';
  return process.env.SHELL || '/bin/bash';
}

function getShellArgs(shellPath) {
  if (process.platform === 'win32') return shellPath.toLowerCase().includes('powershell') ? ['-NoLogo'] : [];
  return ['-l'];
}

// ---------------------------------------------------------------------------
// App Lifecycle
// ---------------------------------------------------------------------------
app.whenReady().then(async () => {
  buildAppMenu();
  createWindow();

  // Notify the renderer about JDK availability once the UI is loaded —
  // drives the "JDK not found" startup toast (this IDE is Java-focused,
  // so the check always runs).
  mainWindow?.webContents.once('did-finish-load', () => {
    mainWindow?.webContents.send('java:status', {
      found: !!JAVA_HOME,
      home: JAVA_HOME || null,
      jreOnly: !JAVA_HOME && hasJreOnly(),
    });
  });

  // Start backend in background
  const backendStarted = await startBackend();
  if (backendStarted) {
    console.log('FastAPI backend started on port', BACKEND_PORT);
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('backend:status', { running: true });
    }
  } else {
    console.warn('FastAPI backend failed to start. Refactoring features will be unavailable.');
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('backend:status', { running: false });
    }
  }

  app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
});

app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });

app.on('before-quit', () => {
  terminals.forEach((term) => { try { term.kill(); } catch (_) {} });
  terminals.clear();
  stopBackend();
});
