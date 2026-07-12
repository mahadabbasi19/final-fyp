// =============================================================================
// preload.js — Secure IPC Bridge
// CodeNova IDE: VS Code-style Desktop Editor
// =============================================================================

const { contextBridge, ipcRenderer } = require('electron');

// ---------------------------------------------------------------------------
// Expose a safe API to the renderer process via contextBridge
// ---------------------------------------------------------------------------
contextBridge.exposeInMainWorld('electronAPI', {

  // --- Dialogs ---
  openFolder: () => ipcRenderer.invoke('dialog:openFolder'),
  getLastFolder: () => ipcRenderer.invoke('workspace:getLastFolder'),
  clearLastFolder: () => ipcRenderer.invoke('workspace:clearLastFolder'),
  openFile: () => ipcRenderer.invoke('dialog:openFile'),
  saveAs: (opts) => ipcRenderer.invoke('dialog:saveAs', opts),

  // --- File System ---
  readDir: (dirPath) => ipcRenderer.invoke('fs:readDir', dirPath),
  readFile: (filePath) => ipcRenderer.invoke('fs:readFile', filePath),
  writeFile: (filePath, content) => ipcRenderer.invoke('fs:writeFile', filePath, content),
  createFile: (filePath) => ipcRenderer.invoke('fs:createFile', filePath),
  createDir: (dirPath) => ipcRenderer.invoke('fs:createDir', dirPath),
  deleteItem: (targetPath) => ipcRenderer.invoke('fs:delete', targetPath),
  renameItem: (oldPath, newPath) => ipcRenderer.invoke('fs:rename', oldPath, newPath),
  statItem: (targetPath) => ipcRenderer.invoke('fs:stat', targetPath),

  // --- Terminal ---
  createTerminal: (opts) => ipcRenderer.invoke('terminal:create', opts),
  writeTerminal: (id, data) => ipcRenderer.send('terminal:write', { id, data }),
  resizeTerminal: (id, cols, rows) => ipcRenderer.send('terminal:resize', { id, cols, rows }),
  killTerminal: (id) => ipcRenderer.send('terminal:kill', { id }),
  onTerminalData: (callback) => {
    const handler = (event, payload) => callback(payload);
    ipcRenderer.on('terminal:data', handler);
    return () => ipcRenderer.removeListener('terminal:data', handler);
  },
  onTerminalExit: (callback) => {
    const handler = (event, payload) => callback(payload);
    ipcRenderer.on('terminal:exit', handler);
    return () => ipcRenderer.removeListener('terminal:exit', handler);
  },

  // --- Run / Execute ---
  runFile: (opts) => ipcRenderer.invoke('run:file', opts),

  // --- Backend (Java Refactoring Engine) ---
  backendHealth: () => ipcRenderer.invoke('backend:health'),
  backendRefactor: (opts) => ipcRenderer.invoke('backend:refactor', opts),
  backendAnalyze: (opts) => ipcRenderer.invoke('backend:analyze', opts),
  backendCheckErrors: (opts) => ipcRenderer.invoke('backend:checkErrors', opts),
  backendStats: () => ipcRenderer.invoke('backend:stats'),
  backendDependencyGraph: (opts) => ipcRenderer.invoke('backend:dependencyGraph', opts),
  backendRefactorReview: (opts) => ipcRenderer.invoke('backend:refactorReview', opts),
  backendRefactorDecision: (opts) => ipcRenderer.invoke('backend:refactorDecision', opts),
  backendChat: (opts) => ipcRenderer.invoke('backend:chat', opts),
  backendChatHealthDashboard: (opts) => ipcRenderer.invoke('backend:chatHealthDashboard', opts),
  openaiKeyStatus: () => ipcRenderer.invoke('backend:openaiKeyStatus'),
  openaiKeySet: (opts) => ipcRenderer.invoke('backend:openaiKeySet', opts),
  openaiKeyClear: () => ipcRenderer.invoke('backend:openaiKeyClear'),

  // --- Git Operations ---
  gitStatus: (opts) => ipcRenderer.invoke('backend:gitStatus', opts),
  gitInit: (opts) => ipcRenderer.invoke('backend:gitInit', opts),
  gitStage: (opts) => ipcRenderer.invoke('backend:gitStage', opts),
  gitStageAll: (opts) => ipcRenderer.invoke('backend:gitStageAll', opts),
  gitUnstage: (opts) => ipcRenderer.invoke('backend:gitUnstage', opts),
  gitDiscard: (opts) => ipcRenderer.invoke('backend:gitDiscard', opts),
  gitCommit: (opts) => ipcRenderer.invoke('backend:gitCommit', opts),
  gitBranches: (opts) => ipcRenderer.invoke('backend:gitBranches', opts),
  gitBranchCreate: (opts) => ipcRenderer.invoke('backend:gitBranchCreate', opts),
  gitBranchSwitch: (opts) => ipcRenderer.invoke('backend:gitBranchSwitch', opts),
  gitBranchDelete: (opts) => ipcRenderer.invoke('backend:gitBranchDelete', opts),
  gitPush: (opts) => ipcRenderer.invoke('backend:gitPush', opts),
  gitPull: (opts) => ipcRenderer.invoke('backend:gitPull', opts),
  gitFetch: (opts) => ipcRenderer.invoke('backend:gitFetch', opts),
  gitDiff: (opts) => ipcRenderer.invoke('backend:gitDiff', opts),
  gitLog: (opts) => ipcRenderer.invoke('backend:gitLog', opts),
  gitStashSave: (opts) => ipcRenderer.invoke('backend:gitStashSave', opts),
  gitStashPop: (opts) => ipcRenderer.invoke('backend:gitStashPop', opts),
  gitStashList: (opts) => ipcRenderer.invoke('backend:gitStashList', opts),
  onBackendStatus: (callback) => {
    const handler = (event, payload) => callback(payload);
    ipcRenderer.on('backend:status', handler);
    return () => ipcRenderer.removeListener('backend:status', handler);
  },
  onJavaStatus: (callback) => {
    const handler = (event, payload) => callback(payload);
    ipcRenderer.on('java:status', handler);
    return () => ipcRenderer.removeListener('java:status', handler);
  },
  javaRedetect: () => ipcRenderer.invoke('java:redetect'),
  javaLocate: () => ipcRenderer.invoke('java:locate'),

  // --- Push to GitHub (standalone subprocess) ---
  pushToGitHub: (opts) => ipcRenderer.invoke('push-to-github', opts),
  githubDeviceStart: (opts) => ipcRenderer.invoke('github:deviceStart', opts),
  githubDeviceWait: (opts) => ipcRenderer.invoke('github:deviceWait', opts),

  // --- Embedded collaboration host ---
  collabHostStart: () => ipcRenderer.invoke('collab:hostStart'),
  collabHostStop: () => ipcRenderer.invoke('collab:hostStop'),
  collabHostInfo: () => ipcRenderer.invoke('collab:hostInfo'),

  // --- Multi-file Dependency Graph ---
  multiFileDependencyGraph: (opts) => ipcRenderer.invoke('backend:multiFileDependencyGraph', opts),
  readJavaFiles: (rootPath) => ipcRenderer.invoke('fs:readJavaFiles', rootPath),

  // --- Refactoring History ---
  getRefactoringHistory: () => ipcRenderer.invoke('backend:getRefactoringHistory'),
  saveRefactoringHistory: (entry) => ipcRenderer.invoke('backend:saveRefactoringHistory', entry),
  clearRefactoringHistory: () => ipcRenderer.invoke('backend:clearRefactoringHistory'),

  // --- Rename Symbol across files ---
  renameSymbol: (opts) => ipcRenderer.invoke('backend:renameSymbol', opts),

  // --- Path helpers ---
  pathSep: () => ipcRenderer.invoke('path:sep'),
  pathBasename: (p) => ipcRenderer.invoke('path:basename', p),
  pathDirname: (p) => ipcRenderer.invoke('path:dirname', p),
  pathJoin: (...parts) => ipcRenderer.invoke('path:join', ...parts),
  pathExtname: (p) => ipcRenderer.invoke('path:extname', p),

  // --- Workspace Search ---
  workspaceSearch: (opts) => ipcRenderer.invoke('workspace:search', opts),

  // --- Menu event listeners ---
  onMenuEvent: (channel, callback) => {
    const handler = (event, ...args) => callback(...args);
    ipcRenderer.on(channel, handler);
    return () => ipcRenderer.removeListener(channel, handler);
  },

  // --- Misc ---
  getAppPath: (name) => ipcRenderer.invoke('app:getPath', name),
  openExternal: (url) => ipcRenderer.invoke('shell:openExternal', url),
});
