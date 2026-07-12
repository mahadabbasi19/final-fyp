// =============================================================================
// renderer.js — Renderer Process Logic
// CodeNova IDE: VS Code-style Desktop Editor
// =============================================================================

(function () {
  'use strict';

  // Global error handler — prevents one broken binding from killing the rest
  window.addEventListener('error', (e) => {
    console.error('[CodeNova] Uncaught error:', e.message, e.filename, e.lineno);
  });
  window.addEventListener('unhandledrejection', (e) => {
    console.error('[CodeNova] Unhandled promise rejection:', e.reason);
  });

  const api = window.electronAPI;

  // =========================================================================
  // State
  // =========================================================================
  const state = {
    workspacePath: null,
    openTabs: [],           // { id, filePath, label, model, isDirty, isUntitled }
    activeTabId: null,
    editor: null,            // Monaco editor instance
    terminal: null,          // xterm Terminal instance
    terminalId: null,        // pty process id from main
    terminalFit: null,       // FitAddon instance
    autoSave: false,
    panelVisible: true,
    sidebarVisible: true,
    nextUntitledId: 1,
    contextMenuTarget: null, // for right-click actions
    backendReady: false,     // FastAPI backend status
    errorCheckTimer: null,   // debounce timer for real-time error checking
    errorCheckInflight: false, // true while a /check-errors request is pending
    errorCheckSeq: 0,        // request id — drop stale responses
    errorCheckLastCode: '',  // skip re-checking identical code
    lastAnalysis: null,      // cached analysis result
    lastRefactoring: null,   // cached refactoring result
    graphExpanded: false,    // graph panel expanded/collapsed
    diffSession: null,       // current diff review session { session_id, ... }
  };

  // =========================================================================
  // Monaco Editor Setup
  // =========================================================================
  function initMonaco() {
    return new Promise((resolve) => {
      // Configure AMD loader for Monaco
      const amdLoader = document.createElement('script');
      amdLoader.src = 'node_modules/monaco-editor/min/vs/loader.js';
      amdLoader.onload = () => {
        window.require.config({
          paths: { vs: 'node_modules/monaco-editor/min/vs' }
        });
        window.require(['vs/editor/editor.main'], () => {
          // Define VS Code Dark+ theme
          monaco.editor.defineTheme('codenova-dark', {
            base: 'vs-dark',
            inherit: true,
            rules: [],
            colors: {
              'editor.background': '#1e1e1e',
              'editor.foreground': '#d4d4d4',
              'editorCursor.foreground': '#aeafad',
              'editor.lineHighlightBackground': '#2a2d2e',
              'editorLineNumber.foreground': '#858585',
              'editorLineNumber.activeForeground': '#c6c6c6',
              'editor.selectionBackground': '#264f78',
              'editor.inactiveSelectionBackground': '#3a3d41',
              'editorIndentGuide.background': '#404040',
              'editorIndentGuide.activeBackground': '#707070',
              'tab.activeBackground': '#1e1e1e',
              'tab.inactiveBackground': '#2d2d2d',
              'sideBar.background': '#252526',
              'activityBar.background': '#333333'
            }
          });

          state.editor = monaco.editor.create(document.getElementById('monaco-container'), {
            value: '',
            language: 'plaintext',
            theme: 'codenova-dark',
            fontSize: 14,
            fontFamily: "'Cascadia Code', 'Fira Code', 'Droid Sans Mono', Consolas, 'Courier New', monospace",
            minimap: { enabled: true },
            scrollBeyondLastLine: true,
            automaticLayout: true,
            tabSize: 4,
            wordWrap: 'off',
            renderWhitespace: 'selection',
            cursorBlinking: 'blink',
            cursorSmoothCaretAnimation: 'on',
            smoothScrolling: true,
            bracketPairColorization: { enabled: true },
            guides: { bracketPairs: true, indentation: true },
            suggest: { snippetsPreventQuickSuggestions: false },
            padding: { top: 8 },
          });

          // Cursor position updates
          state.editor.onDidChangeCursorPosition((e) => {
            const pos = e.position;
            document.getElementById('status-cursor').textContent = `Ln ${pos.lineNumber}, Col ${pos.column}`;
          });

          // Content change → mark dirty
          state.editor.onDidChangeModelContent(() => {
            const tab = getActiveTab();
            if (tab && !tab.isDirty) {
              tab.isDirty = true;
              renderTabs();
            }
            if (state.autoSave && tab) {
              clearTimeout(tab._autoSaveTimer);
              tab._autoSaveTimer = setTimeout(() => saveFile(tab.id), 1000);
            }
            // In-place mutation fix: any edit invalidates the cached
            // analysis / refactor plan so the next user-triggered
            // "Refactor" or "Analyze" runs against the current buffer
            // instead of replaying a stale plan against new code.
            state.lastAnalysis = null;
            state.lastRefactoring = null;
            // Real-time error checking for Java files
            scheduleErrorCheck();
          });

          // Keybindings
          state.editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
            saveFile(state.activeTabId);
          });

          state.editor.addCommand(monaco.KeyCode.F5, () => {
            runCurrentFile();
          });

          // Override Monaco defaults so these shortcuts reach the Electron menu
          state.editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyO, () => {
            openFileDialog();
          });
          state.editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyN, () => {
            createTab('', '', true);
          });
          state.editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyMod.Shift | monaco.KeyCode.KeyS, () => {
            saveAsFile();
          });
          state.editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyMod.Shift | monaco.KeyCode.KeyE, () => {
            document.querySelector('.activitybar-item[data-panel="explorer"]')?.click();
          });
          state.editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyMod.Shift | monaco.KeyCode.KeyF, () => {
            document.querySelector('.activitybar-item[data-panel="search"]')?.click();
          });
          state.editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyMod.Shift | monaco.KeyCode.KeyO, () => {
            openFolderDialog();
          });

          resolve();
        });
      };
      document.head.appendChild(amdLoader);
    });
  }

  // =========================================================================
  // Language Detection
  // =========================================================================
  const EXT_LANG_MAP = {
    '.js': 'javascript', '.jsx': 'javascript',
    '.ts': 'typescript', '.tsx': 'typescript',
    '.py': 'python',
    '.java': 'java',
    '.c': 'c', '.h': 'c',
    '.cpp': 'cpp', '.cc': 'cpp', '.cxx': 'cpp', '.hpp': 'cpp',
    '.cs': 'csharp',
    '.go': 'go',
    '.rs': 'rust',
    '.rb': 'ruby',
    '.php': 'php',
    '.html': 'html', '.htm': 'html',
    '.css': 'css', '.scss': 'scss', '.less': 'less',
    '.json': 'json',
    '.xml': 'xml',
    '.yaml': 'yaml', '.yml': 'yaml',
    '.md': 'markdown',
    '.sql': 'sql',
    '.sh': 'shell', '.bash': 'shell',
    '.ps1': 'powershell',
    '.bat': 'bat', '.cmd': 'bat',
    '.r': 'r',
    '.swift': 'swift',
    '.kt': 'kotlin',
    '.lua': 'lua',
    '.pl': 'perl',
    '.dockerfile': 'dockerfile',
    '.toml': 'toml',
    '.ini': 'ini',
    '.cfg': 'ini',
    '.txt': 'plaintext',
    '.log': 'plaintext',
    '.csv': 'plaintext',
  };

  function detectLanguage(filePath) {
    if (!filePath) return 'plaintext';
    const fileName = filePath.split(/[\\/]/).pop().toLowerCase();
    if (fileName === 'dockerfile') return 'dockerfile';
    if (fileName === 'makefile') return 'makefile';
    const ext = '.' + fileName.split('.').pop();
    return EXT_LANG_MAP[ext] || 'plaintext';
  }

  // =========================================================================
  // File Icon Helper
  // =========================================================================
  function getFileIcon(name, isDir, isOpen) {
    if (isDir) {
      return isOpen
        ? '<i class="codicon codicon-folder-opened icon-folder-open"></i>'
        : '<i class="codicon codicon-folder icon-folder"></i>';
    }
    const ext = name.includes('.') ? name.split('.').pop().toLowerCase() : '';
    const iconMap = {
      'js': 'codicon-file icon-js', 'jsx': 'codicon-file icon-js',
      'ts': 'codicon-file icon-ts', 'tsx': 'codicon-file icon-ts',
      'py': 'codicon-file icon-py',
      'java': 'codicon-file icon-java',
      'html': 'codicon-file icon-html', 'htm': 'codicon-file icon-html',
      'css': 'codicon-file icon-css', 'scss': 'codicon-file icon-css',
      'json': 'codicon-file icon-json',
      'md': 'codicon-file icon-md',
      'xml': 'codicon-file icon-xml',
      'txt': 'codicon-file icon-txt',
    };
    const cls = iconMap[ext] || 'codicon-file icon-default';
    return `<i class="codicon ${cls}"></i>`;
  }

  // =========================================================================
  // Tab Management
  // =========================================================================
  function createTab(filePath, content, isUntitled = false) {
    const existing = state.openTabs.find(t => t.filePath === filePath && !t.isUntitled);
    if (existing) {
      activateTab(existing.id);
      return existing;
    }

    const id = Date.now() + '-' + Math.random().toString(36).substr(2, 5);
    const label = isUntitled
      ? `Untitled-${state.nextUntitledId++}`
      : filePath.split(/[\\/]/).pop();

    const lang = isUntitled ? 'plaintext' : detectLanguage(filePath);
    const model = monaco.editor.createModel(content || '', lang);

    const tab = { id, filePath, label, model, isDirty: false, isUntitled };
    state.openTabs.push(tab);
    activateTab(id);
    return tab;
  }

  function activateTab(tabId) {
    state.activeTabId = tabId;
    const tab = state.openTabs.find(t => t.id === tabId);
    if (!tab) return;

    // Show editor, hide welcome
    document.getElementById('welcome-tab').style.display = 'none';
    document.getElementById('monaco-container').style.display = 'block';

    state.editor.setModel(tab.model);
    tab.model.updateOptions({ tabSize: getUserSettings().tabSize });
    const lang = tab.model.getLanguageId();
    document.getElementById('status-language').textContent = lang.charAt(0).toUpperCase() + lang.slice(1);

    renderTabs();

    // Attach collaboration binding to this file if we're in a workspace.
    if (window.codenovaCollab) window.codenovaCollab.bindActiveTab(tab);

    // Focus editor so keyboard shortcuts work
    setTimeout(() => state.editor.focus(), 50);

    // Auto-update graph when switching to a Java file
    if (isJavaFile(tab) && state.backendReady) {
      updateGraph();
    }
  }

  function closeTab(tabId) {
    const idx = state.openTabs.findIndex(t => t.id === tabId);
    if (idx === -1) return;

    const tab = state.openTabs[idx];
    // Detach any collaboration binding before disposing the model.
    if (window.codenovaCollab) window.codenovaCollab.unbindTab(tab);
    // TODO: prompt save if dirty
    tab.model.dispose();
    state.openTabs.splice(idx, 1);

    if (state.activeTabId === tabId) {
      if (state.openTabs.length > 0) {
        const next = state.openTabs[Math.min(idx, state.openTabs.length - 1)];
        activateTab(next.id);
      } else {
        state.activeTabId = null;
        document.getElementById('welcome-tab').style.display = 'flex';
        document.getElementById('monaco-container').style.display = 'none';
        document.getElementById('status-language').textContent = 'Plain Text';
        document.getElementById('status-cursor').textContent = 'Ln 1, Col 1';
      }
    }
    renderTabs();
  }

  function getActiveTab() {
    return state.openTabs.find(t => t.id === state.activeTabId) || null;
  }

  function renderTabs() {
    const container = document.getElementById('tabs-container');
    container.innerHTML = '';

    state.openTabs.forEach(tab => {
      const el = document.createElement('div');
      el.className = 'tab' + (tab.id === state.activeTabId ? ' active' : '') + (tab.isDirty ? ' modified' : '');
      el.dataset.tabId = tab.id;

      el.innerHTML = `
        <span class="tab-icon">${getFileIcon(tab.label, false, false)}</span>
        <span class="tab-label">${escapeHtml(tab.label)}</span>
        <span class="tab-modified"></span>
        <button class="tab-close"><i class="codicon codicon-close"></i></button>
      `;

      el.addEventListener('click', (e) => {
        if (!e.target.closest('.tab-close')) activateTab(tab.id);
      });
      el.querySelector('.tab-close').addEventListener('click', (e) => {
        e.stopPropagation();
        closeTab(tab.id);
      });

      // Middle-click to close
      el.addEventListener('mousedown', (e) => {
        if (e.button === 1) { e.preventDefault(); closeTab(tab.id); }
      });

      container.appendChild(el);
    });
  }

  // =========================================================================
  // File Operations
  // =========================================================================
  async function openFileDialog() {
    const result = await api.openFile();
    if (!result.canceled) {
      createTab(result.path, result.content);
    }
  }

  async function openFolderDialog() {
    const result = await api.openFolder();
    if (!result.canceled) {
      state.workspacePath = result.path;
      const folderName = result.path.split(/[\\/]/).pop();
      document.getElementById('workspace-name').textContent = folderName.toUpperCase();
      document.getElementById('open-folder-prompt').style.display = 'none';
      document.getElementById('explorer-actions').style.display = 'flex';
      await renderFileTree(result.path, document.getElementById('file-tree'));
      // Auto-refresh git status when folder opens
      setTimeout(() => gitRefresh(), 500);
    }
  }

  async function openFileFromPath(filePath) {
    const existing = state.openTabs.find(t => t.filePath === filePath && !t.isUntitled);
    if (existing) {
      activateTab(existing.id);
      return;
    }
    try {
      const content = await api.readFile(filePath);
      createTab(filePath, content);
    } catch (err) {
      console.error('Failed to open file:', err);
    }
  }

  async function saveFile(tabId) {
    const tab = state.openTabs.find(t => t.id === tabId);
    if (!tab) return;

    const content = tab.model.getValue();

    if (tab.isUntitled) {
      const result = await api.saveAs({ defaultPath: tab.label });
      if (result.canceled) return;
      tab.filePath = result.path;
      tab.label = result.path.split(/[\\/]/).pop();
      tab.isUntitled = false;
      const lang = detectLanguage(tab.filePath);
      monaco.editor.setModelLanguage(tab.model, lang);
    }

    await api.writeFile(tab.filePath, content);
    tab.isDirty = false;
    renderTabs();
  }

  async function saveAsFile() {
    const tab = getActiveTab();
    if (!tab) return;
    const result = await api.saveAs({ defaultPath: tab.label });
    if (result.canceled) return;
    tab.filePath = result.path;
    tab.label = result.path.split(/[\\/]/).pop();
    tab.isUntitled = false;
    tab.isDirty = false;
    const lang = detectLanguage(tab.filePath);
    monaco.editor.setModelLanguage(tab.model, lang);
    await api.writeFile(tab.filePath, tab.model.getValue());
    renderTabs();
  }

  // =========================================================================
  // File Tree / Explorer
  // =========================================================================
  async function renderFileTree(dirPath, container, depth = 0) {
    container.innerHTML = '';
    try {
      const items = await api.readDir(dirPath);
      items.forEach(item => {
        const itemEl = document.createElement('div');

        if (item.isDirectory) {
          const headerEl = document.createElement('div');
          headerEl.className = 'tree-item';
          headerEl.style.paddingLeft = (8 + depth * 16) + 'px';
          headerEl.dataset.path = item.path;
          headerEl.dataset.isDir = 'true';
          headerEl.innerHTML = `
            <span class="tree-chevron codicon codicon-chevron-down collapsed"></span>
            ${getFileIcon(item.name, true, false)}
            <span class="tree-label">${escapeHtml(item.name)}</span>
          `;

          const childContainer = document.createElement('div');
          childContainer.className = 'tree-item-children';

          let loaded = false;
          headerEl.addEventListener('click', async () => {
            const chevron = headerEl.querySelector('.tree-chevron');
            const isExpanded = childContainer.classList.contains('expanded');
            if (isExpanded) {
              childContainer.classList.remove('expanded');
              chevron.classList.add('collapsed');
              headerEl.querySelector('.codicon-folder-opened')?.classList.replace('codicon-folder-opened', 'codicon-folder');
            } else {
              if (!loaded) {
                await renderFileTree(item.path, childContainer, depth + 1);
                loaded = true;
              }
              childContainer.classList.add('expanded');
              chevron.classList.remove('collapsed');
              headerEl.querySelector('.codicon-folder')?.classList.replace('codicon-folder', 'codicon-folder-opened');
            }
          });

          // Context menu
          headerEl.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            showContextMenu(e.clientX, e.clientY, item);
          });

          itemEl.appendChild(headerEl);
          itemEl.appendChild(childContainer);
        } else {
          const fileEl = document.createElement('div');
          fileEl.className = 'tree-item';
          fileEl.style.paddingLeft = (8 + depth * 16 + 16) + 'px';
          fileEl.dataset.path = item.path;
          fileEl.innerHTML = `
            ${getFileIcon(item.name, false, false)}
            <span class="tree-label">${escapeHtml(item.name)}</span>
          `;

          fileEl.addEventListener('click', () => {
            // Remove active from all
            document.querySelectorAll('.tree-item.active').forEach(el => el.classList.remove('active'));
            fileEl.classList.add('active');
            openFileFromPath(item.path);
          });

          fileEl.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            showContextMenu(e.clientX, e.clientY, item);
          });

          itemEl.appendChild(fileEl);
        }

        container.appendChild(itemEl);
      });
    } catch (err) {
      console.error('Failed to render file tree:', err);
    }
  }

  // Refresh the entire tree
  async function refreshFileTree() {
    if (!state.workspacePath) return;
    try {
      await renderFileTree(state.workspacePath, document.getElementById('file-tree'));
    } catch (err) {
      console.error('Refresh file tree failed:', err);
    }
  }

  // =========================================================================
  // Context Menu
  // =========================================================================
  function showContextMenu(x, y, target) {
    state.contextMenuTarget = target;
    const menu = document.getElementById('context-menu');
    menu.style.display = 'block';
    menu.style.left = x + 'px';
    menu.style.top = y + 'px';

    // Ensure it stays in viewport
    const rect = menu.getBoundingClientRect();
    if (rect.right > window.innerWidth) menu.style.left = (x - rect.width) + 'px';
    if (rect.bottom > window.innerHeight) menu.style.top = (y - rect.height) + 'px';
  }

  function hideContextMenu() {
    document.getElementById('context-menu').style.display = 'none';
    state.contextMenuTarget = null;
  }

  document.addEventListener('click', hideContextMenu);
  document.addEventListener('contextmenu', (e) => {
    if (!e.target.closest('.tree-item')) hideContextMenu();
  });

  // Context menu actions
  document.querySelectorAll('.context-menu-item').forEach(item => {
    item.addEventListener('click', async () => {
      const action = item.dataset.action;
      const target = state.contextMenuTarget;
      if (!target) return;

      const parentDir = target.isDirectory ? target.path : target.path.substring(0, target.path.lastIndexOf(target.name.length > 0 ? target.name : ''));

      switch (action) {
        case 'newFile': {
          const name = await showInlineInput('File name...');
          if (name) {
            try {
              const sep = (await api.pathSep());
              await api.createFile(target.isDirectory ? target.path + sep + name : parentDir + name);
              refreshFileTree();
            } catch (err) { showNotification(err.message || 'Failed to create file', 'error'); }
          }
          break;
        }
        case 'newFolder': {
          const name = await showInlineInput('Folder name...');
          if (name) {
            try {
              const sep = (await api.pathSep());
              await api.createDir(target.isDirectory ? target.path + sep + name : parentDir + name);
              refreshFileTree();
            } catch (err) { showNotification(err.message || 'Failed to create folder', 'error'); }
          }
          break;
        }
        case 'rename': {
          const newName = await showInlineInput('New name...');
          if (newName && newName !== target.name) {
            const dir = target.path.substring(0, target.path.length - target.name.length);
            await api.renameItem(target.path, dir + newName);
            refreshFileTree();
          }
          break;
        }
        case 'delete': {
          if (confirm(`Delete "${target.name}"?`)) {
            await api.deleteItem(target.path);
            refreshFileTree();
          }
          break;
        }
        case 'copyPath': {
          navigator.clipboard.writeText(target.path);
          break;
        }
      }
      hideContextMenu();
    });
  });

  // =========================================================================
  // Integrated Terminal (xterm.js)
  // =========================================================================
  async function initTerminal() {
    try {
      // Load xterm CSS
      const xtermCss = document.createElement('link');
      xtermCss.rel = 'stylesheet';
      xtermCss.href = 'node_modules/xterm/css/xterm.css';
      document.head.appendChild(xtermCss);

      // Temporarily hide AMD define so xterm UMD scripts attach to window
      const savedDefine = window.define;
      window.define = undefined;

      await loadScript('node_modules/xterm/lib/xterm.js');
      await loadScript('node_modules/xterm-addon-fit/lib/xterm-addon-fit.js');
      await loadScript('node_modules/xterm-addon-web-links/lib/xterm-addon-web-links.js');

      // Restore AMD define for Monaco
      window.define = savedDefine;

      // xterm UMD attaches to window
      const TerminalCtor = window.Terminal?.Terminal || window.Terminal;
      const FitAddonCtor = window.FitAddon?.FitAddon || window.FitAddon;
      const WebLinksAddonCtor = window.WebLinksAddon?.WebLinksAddon || window.WebLinksAddon;

      if (!TerminalCtor) {
        throw new Error('xterm Terminal class not found after script load');
      }

      const fitAddon = FitAddonCtor ? new FitAddonCtor() : null;
      const webLinksAddon = WebLinksAddonCtor ? new WebLinksAddonCtor() : null;

      const term = new TerminalCtor({
        fontFamily: "'Cascadia Code', 'Fira Code', Consolas, 'Courier New', monospace",
        fontSize: 13,
        theme: {
          background: '#1e1e1e',
          foreground: '#cccccc',
          cursor: '#aeafad',
          selectionBackground: '#264f78',
          black: '#000000',
          red: '#cd3131',
          green: '#0dbc79',
          yellow: '#e5e510',
          blue: '#2472c8',
          magenta: '#bc3fbc',
          cyan: '#11a8cd',
          white: '#e5e5e5',
          brightBlack: '#666666',
          brightRed: '#f14c4c',
          brightGreen: '#23d18b',
          brightYellow: '#f5f543',
          brightBlue: '#3b8eea',
          brightMagenta: '#d670d6',
          brightCyan: '#29b8db',
          brightWhite: '#e5e5e5'
        },
        cursorBlink: true,
        allowTransparency: true,
      });

      if (fitAddon) term.loadAddon(fitAddon);
      if (webLinksAddon) term.loadAddon(webLinksAddon);

      const container = document.getElementById('terminal-container');
      term.open(container);

      // Wait a tick for DOM to settle
      await new Promise(r => setTimeout(r, 100));
      if (fitAddon) fitAddon.fit();

      state.terminal = term;
      state.terminalFit = fitAddon;

      // Create pty process
      const cwd = state.workspacePath || undefined;
      const id = await api.createTerminal({ cols: term.cols, rows: term.rows, cwd });
      state.terminalId = id;

      // Wire: xterm → pty
      term.onData((data) => {
        api.writeTerminal(id, data);
      });

      // Wire: pty → xterm
      api.onTerminalData(({ id: tid, data }) => {
        if (tid === state.terminalId) term.write(data);
      });

      api.onTerminalExit(({ id: tid }) => {
        if (tid === state.terminalId) {
          term.writeln('\r\n\x1b[90m[Process exited]\x1b[0m');
          state.terminalId = null;
        }
      });

      // Handle resize
      const resizeObserver = new ResizeObserver(() => {
        try {
          if (fitAddon) fitAddon.fit();
          if (state.terminalId) {
            api.resizeTerminal(state.terminalId, term.cols, term.rows);
          }
        } catch (_) {}
      });
      resizeObserver.observe(container);

    } catch (err) {
      console.warn('Terminal init failed:', err);
      document.getElementById('terminal-container').innerHTML =
        '<div style="padding:12px;color:#969696;">Terminal unavailable. Install node-pty and xterm: npm install node-pty xterm xterm-addon-fit</div>';
    }
  }

  // Load a script tag and return a promise
  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = src;
      script.onload = resolve;
      script.onerror = () => reject(new Error(`Failed to load script: ${src}`));
      document.head.appendChild(script);
    });
  }

  // =========================================================================
  // Backend Integration (Java Refactoring Engine)
  // =========================================================================

  function updateBackendStatus(running) {
    state.backendReady = running;
    const el = document.getElementById('backend-status');
    if (running) {
      el.className = 'refactoring-status connected';
      el.innerHTML = '<i class="codicon codicon-circle-filled"></i><span>Engine connected</span>';
    } else {
      el.className = 'refactoring-status disconnected';
      el.innerHTML = '<i class="codicon codicon-circle-filled"></i><span>Engine offline</span>';
    }
    // Enable/disable refactoring buttons
    document.querySelectorAll('.btn-refactor').forEach(btn => {
      btn.disabled = !running;
    });
  }

  // Listen for backend status from main process
  api.onBackendStatus(({ running }) => updateBackendStatus(running));

  // Check backend health on startup
  async function checkBackendHealth() {
    try {
      const result = await api.backendHealth();
      updateBackendStatus(result.status === 'healthy');
    } catch {
      updateBackendStatus(false);
    }
  }

  function getActiveJavaCode() {
    const tab = getActiveTab();
    if (!tab) return null;
    const model = tab.model;
    if (!model) return null;
    return model.getValue();
  }

  function isJavaFile(tab) {
    if (!tab) return false;
    if (tab.filePath) return tab.filePath.endsWith('.java');
    return tab.label?.endsWith('.java');
  }

  function getSelectedRefactorings() {
    const checkboxes = document.querySelectorAll('#refactoring-options input[type="checkbox"]:checked');
    return Array.from(checkboxes).map(cb => cb.value);
  }

  function appendRefactoringOutput(text) {
    const el = document.getElementById('refactoring-output');
    el.textContent += text;
    el.scrollTop = el.scrollHeight;
  }

  // --- Refactor (Preview with Diff) ---
  async function refactorCode() {
    const tab = getActiveTab();
    const code = getActiveJavaCode();
    if (!code) { showNotification('Open a Java file first.', 'error'); return; }
    if (!state.backendReady) { showNotification('Backend is not running.', 'error'); return; }

    const selected = getSelectedRefactorings();
    appendRefactoringOutput('\n[Refactoring] Previewing: ' + selected.join(', ') + '...\n');
    showPanel('refactoring-output-panel');
    ensurePanelVisible();

    try {
      const result = await api.backendRefactorReview({
        java_code: code,
        selected_refactorings: selected.length > 0 ? selected : null
      });

      if (result.detail) {
        showNotification('Refactoring failed: ' + result.detail, 'error');
        appendRefactoringOutput('[Error] ' + result.detail + '\n');
        return;
      }

      state.diffSession = result;

      // Handle empty diff (no changes needed)
      if (!result.diff || result.diff.trim() === '') {
        showNotification('Code is already clean — no changes needed.', 'info');
        appendRefactoringOutput('[Info] No refactoring changes needed — code is already clean.\n');
        state.diffSession = null;
        renderRefactoringActions(result.actions || []);
        if (result.metrics_before && result.metrics_after) {
          renderMetricsComparison(result.metrics_before, result.metrics_after);
        }
        return;
      }

      showDiffOverlay(result);
      appendRefactoringOutput('[Preview] Diff ready — Accept or Reject changes.\n');

      // Show actions in sidebar
      renderRefactoringActions(result.actions || []);
      if (result.metrics_before && result.metrics_after) {
        renderMetricsComparison(result.metrics_before, result.metrics_after);
      }

    } catch (err) {
      showNotification('Refactoring error: ' + (err.message || 'Unknown error'), 'error');
      appendRefactoringOutput('[Error] ' + (err.message || 'Unknown error') + '\n');
    }
  }

  // --- Diff Overlay (Monaco Diff Editor) ---
  let diffEditorInstance = null;

  function showDiffOverlay(result) {
    const overlay = document.getElementById('diff-overlay');
    const diffContainer = document.getElementById('diff-editor-container');
    const summary = document.getElementById('diff-summary');

    // Get original and modified code
    const originalCode = result.original_code || '';
    const modifiedCode = result.refactored_code || '';

    // Count changes
    const origLines = originalCode.split('\n');
    const modLines = modifiedCode.split('\n');
    const added = modLines.length - origLines.length;
    summary.textContent = added >= 0 ? `+${added} lines` : `${added} lines`;

    overlay.style.display = 'flex';

    // Dispose previous diff editor
    if (diffEditorInstance) {
      diffEditorInstance.dispose();
      diffEditorInstance = null;
    }

    // Create Monaco Diff Editor
    setTimeout(() => {
      diffEditorInstance = monaco.editor.createDiffEditor(diffContainer, {
        theme: 'codenova-dark',
        readOnly: true,
        automaticLayout: true,
        renderSideBySide: true,
        enableSplitViewResizing: true,
        originalEditable: false,
        fontSize: 13,
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
      });

      const originalModel = monaco.editor.createModel(originalCode, 'java');
      const modifiedModel = monaco.editor.createModel(modifiedCode, 'java');

      diffEditorInstance.setModel({
        original: originalModel,
        modified: modifiedModel,
      });
    }, 50);
  }

  function hideDiffOverlay() {
    document.getElementById('diff-overlay').style.display = 'none';
    if (diffEditorInstance) {
      diffEditorInstance.dispose();
      diffEditorInstance = null;
    }
    state.diffSession = null;
  }

  async function acceptRefactoring() {
    if (!state.diffSession) return;
    try {
      const result = await api.backendRefactorDecision({
        session_id: state.diffSession.session_id,
        action: 'accept'
      });
      if (result.final_code) {
        const tab = getActiveTab();
        if (tab && tab.model) {
          // Save history before applying
          try {
            await api.saveRefactoringHistory({
              timestamp: new Date().toISOString(),
              file_path: tab.filePath || tab.label,
              actions: state.diffSession.actions || [],
              original_code: state.diffSession.original_code || '',
              refactored_code: result.final_code,
              metrics_before: state.diffSession.metrics_before || null,
              metrics_after: state.diffSession.metrics_after || null,
            });
          } catch (_) {}

          tab.model.setValue(result.final_code);
          tab.isDirty = true;
          renderTabs();
        }
      }
      appendRefactoringOutput('[Accepted] Refactored code applied.\n');
    } catch (err) {
      appendRefactoringOutput('[Error] ' + err.message + '\n');
    }
    hideDiffOverlay();
  }

  async function rejectRefactoring() {
    if (!state.diffSession) return;
    try {
      await api.backendRefactorDecision({
        session_id: state.diffSession.session_id,
        action: 'reject'
      });
      appendRefactoringOutput('[Rejected] Changes discarded.\n');
    } catch (err) {
      // Session may have expired - that's fine
    }
    hideDiffOverlay();
  }

  // --- Dependency Graph ---
  async function updateGraph() {
    const code = getActiveJavaCode();
    const canvasWrapper = document.getElementById('graph-canvas-wrapper');
    const emptyState = document.getElementById('graph-empty');
    const canvas = document.getElementById('graph-canvas');

    if (!code || !state.backendReady || !isJavaFile(getActiveTab())) {
      if (emptyState) emptyState.style.display = 'flex';
      return;
    }

    try {
      const result = await api.backendDependencyGraph({ java_code: code });
      if (result.detail) return;

      if (emptyState) emptyState.style.display = 'none';
      drawRadarChart(canvas, result.radar);
    } catch (err) {
      console.warn('Graph update failed:', err.message);
    }
  }

  function drawRadarChart(canvas, radar) {
    if (!radar || !radar.labels) return;
    const ctx = canvas.getContext('2d');
    const rect = canvas.parentElement.getBoundingClientRect();
    canvas.width = rect.width * (window.devicePixelRatio || 1);
    canvas.height = rect.height * (window.devicePixelRatio || 1);
    ctx.scale(window.devicePixelRatio || 1, window.devicePixelRatio || 1);

    const w = rect.width;
    const h = rect.height;
    const cx = w / 2;
    const cy = h / 2;
    const r = Math.min(cx, cy) - 30;
    const labels = radar.labels;
    const values = radar.values;
    const n = labels.length;
    const angleStep = (2 * Math.PI) / n;
    const startAngle = -Math.PI / 2;

    ctx.clearRect(0, 0, w, h);

    // Draw grid rings
    for (let ring = 1; ring <= 5; ring++) {
      const ringR = (r / 5) * ring;
      ctx.beginPath();
      for (let i = 0; i <= n; i++) {
        const angle = startAngle + i * angleStep;
        const x = cx + ringR * Math.cos(angle);
        const y = cy + ringR * Math.sin(angle);
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.strokeStyle = 'rgba(255,255,255,0.08)';
      ctx.lineWidth = 1;
      ctx.stroke();
    }

    // Draw axes
    for (let i = 0; i < n; i++) {
      const angle = startAngle + i * angleStep;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(cx + r * Math.cos(angle), cy + r * Math.sin(angle));
      ctx.strokeStyle = 'rgba(255,255,255,0.1)';
      ctx.stroke();
    }

    // Draw data polygon
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const angle = startAngle + i * angleStep;
      const val = (values[i] / 100) * r;
      const x = cx + val * Math.cos(angle);
      const y = cy + val * Math.sin(angle);
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.fillStyle = 'rgba(127, 86, 217, 0.25)';
    ctx.fill();
    ctx.strokeStyle = '#7f56d9';
    ctx.lineWidth = 2;
    ctx.stroke();

    // Draw data points
    for (let i = 0; i < n; i++) {
      const angle = startAngle + i * angleStep;
      const val = (values[i] / 100) * r;
      const x = cx + val * Math.cos(angle);
      const y = cy + val * Math.sin(angle);
      ctx.beginPath();
      ctx.arc(x, y, 4, 0, 2 * Math.PI);
      ctx.fillStyle = '#7f56d9';
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }

    // Draw labels
    ctx.font = '10px "Segoe UI", sans-serif';
    ctx.fillStyle = '#ccc';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    for (let i = 0; i < n; i++) {
      const angle = startAngle + i * angleStep;
      const lx = cx + (r + 18) * Math.cos(angle);
      const ly = cy + (r + 18) * Math.sin(angle);
      ctx.fillText(labels[i], lx, ly);
    }

    // Draw value labels on points
    ctx.font = '9px "Segoe UI", sans-serif';
    ctx.fillStyle = '#a78bfa';
    for (let i = 0; i < n; i++) {
      const angle = startAngle + i * angleStep;
      const val = (values[i] / 100) * r;
      const x = cx + val * Math.cos(angle);
      const y = cy + val * Math.sin(angle) - 10;
      ctx.fillText(Math.round(values[i]), x, y);
    }
  }

  // --- Analyze Code ---
  async function analyzeCode() {
    const code = getActiveJavaCode();
    if (!code) { appendRefactoringOutput('[Error] Open a Java file first.\n'); return; }
    if (!state.backendReady) { appendRefactoringOutput('[Error] Backend is not running.\n'); return; }

    appendRefactoringOutput('\n[Analyzing] Scanning code...\n');

    try {
      const result = await api.backendAnalyze({ java_code: code });
      state.lastAnalysis = result;

      if (result.detail) {
        appendRefactoringOutput('[Error] ' + result.detail + '\n');
        return;
      }

      // Render code smells
      renderCodeSmells(result.code_smells || []);
      // Render opportunities
      renderOpportunities(result.refactoring_opportunities || []);
      // Render metrics
      if (result.metrics) renderMetrics(result.metrics);

      appendRefactoringOutput('[Done] Found ' + (result.code_smells?.length || 0) +
        ' smells, ' + (result.refactoring_opportunities?.length || 0) + ' opportunities.\n');

      // Switch to analysis panel
      document.querySelector('.activitybar-item[data-panel="analysis"]')?.click();

    } catch (err) {
      appendRefactoringOutput('[Error] ' + err.message + '\n');
    }
  }

  // --- Check Errors ---
  async function checkErrors() {
    const code = getActiveJavaCode();
    if (!code) return;
    if (!state.backendReady) return;

    // Skip identical content (same code already checked).
    if (code === state.errorCheckLastCode) return;
    state.errorCheckLastCode = code;

    const seq = ++state.errorCheckSeq;
    state.errorCheckInflight = true;
    try {
      // project_root enables cross-file symbol resolution (javac -sourcepath).
      const result = await api.backendCheckErrors({ java_code: code, project_root: state.workspacePath || null });
      // Drop stale responses if user kept typing.
      if (seq !== state.errorCheckSeq) return;
      if (result.detail) return;
      renderProblems(result);
    } catch (err) {
      console.warn('Error check failed:', err.message);
    } finally {
      if (seq === state.errorCheckSeq) state.errorCheckInflight = false;
    }
  }

  // --- Real-time error checking for Java files ---
  // 350ms debounce — feels near-real-time while staying responsive under load.
  function scheduleErrorCheck() {
    if (state.errorCheckTimer) clearTimeout(state.errorCheckTimer);
    state.errorCheckTimer = setTimeout(() => {
      const tab = getActiveTab();
      if (tab && isJavaFile(tab) && state.backendReady) {
        checkErrors();
      }
    }, 350);
  }

  // --- Render functions ---

  function renderRefactoringActions(actions) {
    const container = document.getElementById('refactoring-actions-list');
    if (!actions.length) {
      container.innerHTML = '<p class="muted">No refactoring actions performed.</p>';
      return;
    }
    container.innerHTML = actions.map(a => `
      <div class="refactor-action-item">
        <div class="action-type">${escapeHtml(a.action_type || 'refactoring')}</div>
        <div class="action-desc">${escapeHtml(a.description || '')}</div>
      </div>
    `).join('');
  }

  function renderMetrics(metrics) {
    const container = document.getElementById('metrics-display');
    const rows = [
      ['Lines of Code', metrics.total_lines],
      ['Code Lines', metrics.code_lines],
      ['Comments', metrics.comment_lines],
      ['Methods', metrics.total_methods],
      ['Classes', metrics.total_classes],
      ['Fields', metrics.total_fields],
      ['Avg Complexity', metrics.avg_complexity?.toFixed(1)],
      ['Max Complexity', metrics.max_complexity],
      ['Max Nesting', metrics.max_nesting],
      ['Long Methods', metrics.long_methods],
      ['Large Classes', metrics.large_classes],
      ['Duplicates', metrics.duplicate_blocks],
    ];
    container.innerHTML = rows.map(([label, val]) => `
      <div class="metric-row">
        <span class="metric-label">${label}</span>
        <span class="metric-value">${val ?? '-'}</span>
      </div>
    `).join('');
  }

  function renderMetricsComparison(before, after) {
    const container = document.getElementById('metrics-display');
    const keys = ['total_lines', 'code_lines', 'total_methods', 'avg_complexity', 'max_complexity', 'long_methods', 'large_classes', 'duplicate_blocks'];
    const labels = {
      total_lines: 'Lines', code_lines: 'Code Lines', total_methods: 'Methods',
      avg_complexity: 'Avg Complexity', max_complexity: 'Max Complexity',
      long_methods: 'Long Methods', large_classes: 'Large Classes', duplicate_blocks: 'Duplicates'
    };
    container.innerHTML = keys.map(k => {
      const b = before[k] ?? 0;
      const a = after[k] ?? 0;
      const diff = a - b;
      const cls = diff < 0 ? 'metric-improved' : diff > 0 ? 'metric-degraded' : '';
      const arrow = diff < 0 ? '↓' : diff > 0 ? '↑' : '=';
      return `
        <div class="metric-row">
          <span class="metric-label">${labels[k] || k}</span>
          <span class="metric-value ${cls}">${b} → ${a} ${arrow}</span>
        </div>
      `;
    }).join('');
  }

  function renderCodeSmells(smells) {
    const container = document.getElementById('smells-list');
    if (!smells.length) {
      container.innerHTML = '<p class="muted">No code smells detected.</p>';
      return;
    }
    container.innerHTML = smells.map(s => `
      <div class="smell-item">
        <span class="smell-severity ${(s.severity || 'warning').toLowerCase()}">${escapeHtml(s.severity || 'WARNING')}</span>
        <span style="color:var(--text-secondary);margin-left:4px;">${escapeHtml(s.type || '')}</span>
        <div style="color:var(--text-muted);margin-top:2px;">${escapeHtml(s.description || '')}</div>
      </div>
    `).join('');
  }

  function renderOpportunities(opportunities) {
    const container = document.getElementById('opportunities-list');
    if (!opportunities.length) {
      container.innerHTML = '<p class="muted">No refactoring opportunities found.</p>';
      return;
    }
    container.innerHTML = opportunities.map(o => `
      <div class="opportunity-item">
        <span style="color:#89d185;font-weight:600;font-size:10px;text-transform:uppercase;">${escapeHtml(o.type || '')}</span>
        <div style="color:var(--text-secondary);margin-top:2px;">${escapeHtml(o.description || '')}</div>
        ${o.recommendation ? `<div style="color:var(--accent);margin-top:2px;font-style:italic;">${escapeHtml(o.recommendation)}</div>` : ''}
      </div>
    `).join('');
  }

  function renderProblems(result) {
    const container = document.getElementById('problems-list');
    const all = [
      ...(result.syntax_errors || []).map(e => ({ ...e, icon: 'error' })),
      ...(result.runtime_errors || []).map(e => ({ ...e, icon: 'warning' })),
      ...(result.warnings || []).map(e => ({ ...e, icon: 'warning' }))
    ];

    // Update badge
    const badge = document.getElementById('problems-count');
    const errorCount = result.syntax_errors?.length || 0;
    const warnCount = (result.runtime_errors?.length || 0) + (result.warnings?.length || 0);
    if (errorCount + warnCount > 0) {
      badge.textContent = errorCount + warnCount;
      badge.style.display = 'inline-block';
    } else {
      badge.style.display = 'none';
    }

    // Update status bar
    document.getElementById('status-errors').innerHTML =
      `<i class="codicon codicon-error"></i> ${errorCount} <i class="codicon codicon-warning"></i> ${warnCount}`;

    if (!all.length) {
      container.innerHTML = '<p class="muted">No problems detected.</p>';
      return;
    }

    container.innerHTML = all.map(p => `
      <div class="problem-item" data-line="${p.line || 0}">
        <i class="codicon codicon-${p.icon}"></i>
        <span class="problem-text">${escapeHtml(p.message || '')}${p.suggestion ? ' — ' + escapeHtml(p.suggestion) : ''}</span>
        <span class="problem-location">Ln ${p.line || '?'}, Col ${p.column || '?'}</span>
      </div>
    `).join('');

    // Click on problem to go to line
    container.querySelectorAll('.problem-item').forEach(el => {
      el.addEventListener('click', () => {
        const line = parseInt(el.dataset.line);
        if (state.editor && line > 0) {
          state.editor.revealLineInCenter(line);
          state.editor.setPosition({ lineNumber: line, column: 1 });
          state.editor.focus();
        }
      });
    });

    // Also set Monaco markers
    if (state.editor) {
      const model = state.editor.getModel();
      if (model) {
        const markers = all.map(p => ({
          severity: p.icon === 'error' ? monaco.MarkerSeverity.Error : monaco.MarkerSeverity.Warning,
          message: p.message || '',
          startLineNumber: p.line || 1,
          startColumn: p.column || 1,
          endLineNumber: p.line || 1,
          endColumn: (p.column || 1) + 10
        }));
        monaco.editor.setModelMarkers(model, 'java-errors', markers);
      }
    }
  }

  // =========================================================================
  // Run File
  // =========================================================================
  async function runCurrentFile() {
    const tab = getActiveTab();
    if (!tab || tab.isUntitled) {
      appendOutput('[Error] Save the file first before running.\n');
      showPanel('output-panel');
      ensurePanelVisible();
      return;
    }

    // Save before running
    if (tab.isDirty) await saveFile(tab.id);

    try {
      const result = await api.runFile({
        filePath: tab.filePath,
        cwd: state.workspacePath || undefined
      });
      const command = result.command;

      // Show terminal panel
      showPanel('terminal-panel');
      ensurePanelVisible();

      // Auto-create terminal if it doesn't exist
      if (state.terminalId == null && state.terminal) {
        try {
          const cwd = state.workspacePath || undefined;
          const id = await api.createTerminal({ cols: state.terminal.cols, rows: state.terminal.rows, cwd });
          state.terminalId = id;
        } catch (termErr) {
          console.error('[Run] Failed to recreate terminal:', termErr);
        }
      }

      // Send command to terminal
      if (state.terminalId != null && state.terminal) {
        state.terminal.writeln('');
        api.writeTerminal(state.terminalId, command + '\r');
      } else {
        appendOutput(`[Run] ${command}\n`);
        appendOutput('[Error] No terminal available. Create a new terminal first.\n');
        showPanel('output-panel');
        ensurePanelVisible();
      }
    } catch (err) {
      console.error('[Run] Error:', err);
      appendOutput(`[Error] ${err.message}\n`);
      showPanel('output-panel');
      ensurePanelVisible();
    }
  }

  function appendOutput(text) {
    const el = document.getElementById('output-content');
    el.textContent += text;
    el.scrollTop = el.scrollHeight;
  }

  function showNotification(message, type = 'info') {
    const el = document.createElement('div');
    el.style.cssText = `position:fixed;top:12px;right:12px;z-index:10000;padding:10px 18px;border-radius:4px;font-size:13px;color:#fff;max-width:400px;box-shadow:0 4px 12px rgba(0,0,0,.4);transition:opacity .3s;`;
    el.style.background = type === 'error' ? '#a1260d' : '#007acc';
    el.textContent = message;
    document.body.appendChild(el);
    setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 300); }, 3500);
  }

  // =========================================================================
  // Activity Bar & Sidebar
  // =========================================================================
  document.querySelectorAll('.activitybar-item[data-panel]').forEach(btn => {
    btn.addEventListener('click', () => {
      const panel = btn.dataset.panel;
      const wasActive = btn.classList.contains('active');

      // Toggle sidebar if clicking the same button
      if (wasActive) {
        state.sidebarVisible = !state.sidebarVisible;
        document.getElementById('sidebar').classList.toggle('collapsed', !state.sidebarVisible);
        return;
      }

      // Switch panel
      document.querySelectorAll('.activitybar-item').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      document.querySelectorAll('.sidebar-panel').forEach(p => p.classList.remove('active'));
      document.getElementById(`panel-${panel}`).classList.add('active');

      const titles = { explorer: 'EXPLORER', search: 'SEARCH', 'source-control': 'SOURCE CONTROL', extensions: 'EXTENSIONS', refactoring: 'REFACTORING', analysis: 'CODE ANALYSIS', chat: 'CODENOVA AI', dependency: 'DEPENDENCY GRAPH', history: 'REFACTORING HISTORY' };
      document.getElementById('sidebar-title').textContent = titles[panel] || panel.toUpperCase();

      if (!state.sidebarVisible) {
        state.sidebarVisible = true;
        document.getElementById('sidebar').classList.remove('collapsed');
      }
    });
  });

  // =========================================================================
  // Bottom Panel Tabs
  // =========================================================================
  document.querySelectorAll('.panel-tab[data-target]').forEach(tab => {
    tab.addEventListener('click', () => {
      showPanel(tab.dataset.target);
    });
  });

  function showPanel(targetId) {
    document.querySelectorAll('.panel-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.panel-content').forEach(p => p.classList.remove('active'));

    const tab = document.querySelector(`.panel-tab[data-target="${targetId}"]`);
    const panel = document.getElementById(targetId);
    if (tab) tab.classList.add('active');
    if (panel) panel.classList.add('active');

    // Fit terminal if switching to terminal
    if (targetId === 'terminal-panel' && state.terminalFit) {
      setTimeout(() => state.terminalFit.fit(), 50);
    }
  }

  function ensurePanelVisible() {
    const panel = document.getElementById('bottom-panel');
    if (panel.classList.contains('collapsed')) {
      panel.classList.remove('collapsed');
      state.panelVisible = true;
    }
  }

  // Toggle panel
  document.getElementById('btn-toggle-panel').addEventListener('click', () => {
    const panel = document.getElementById('bottom-panel');
    state.panelVisible = !state.panelVisible;
    panel.classList.toggle('collapsed', !state.panelVisible);
    if (state.panelVisible && state.terminalFit) {
      setTimeout(() => state.terminalFit.fit(), 50);
    }
  });

  // New terminal
  document.getElementById('btn-new-terminal').addEventListener('click', async () => {
    if (state.terminal) {
      state.terminal.clear();
      if (state.terminalId) {
        api.killTerminal(state.terminalId);
      }
      const cwd = state.workspacePath || undefined;
      const id = await api.createTerminal({ cols: state.terminal.cols, rows: state.terminal.rows, cwd });
      state.terminalId = id;
    }
  });

  // Kill terminal
  document.getElementById('btn-kill-terminal').addEventListener('click', () => {
    if (state.terminalId) {
      api.killTerminal(state.terminalId);
      state.terminalId = null;
    }
  });

  // =========================================================================
  // Sidebar Resize
  // =========================================================================
  {
    const handle = document.getElementById('sidebar-resize');
    const sidebar = document.getElementById('sidebar');
    let startX, startWidth;

    handle.addEventListener('mousedown', (e) => {
      startX = e.clientX;
      startWidth = sidebar.offsetWidth;
      handle.classList.add('active');
      document.addEventListener('mousemove', onMouseMove);
      document.addEventListener('mouseup', onMouseUp);
      e.preventDefault();
    });

    function onMouseMove(e) {
      const newWidth = startWidth + (e.clientX - startX);
      sidebar.style.width = Math.max(170, Math.min(600, newWidth)) + 'px';
    }

    function onMouseUp() {
      handle.classList.remove('active');
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    }
  }

  // =========================================================================
  // Panel Resize
  // =========================================================================
  {
    const handle = document.getElementById('panel-resize');
    const panel = document.getElementById('bottom-panel');
    let startY, startHeight;

    handle.addEventListener('mousedown', (e) => {
      startY = e.clientY;
      startHeight = panel.offsetHeight;
      handle.classList.add('active');
      document.addEventListener('mousemove', onMouseMove);
      document.addEventListener('mouseup', onMouseUp);
      e.preventDefault();
    });

    function onMouseMove(e) {
      const newHeight = startHeight - (e.clientY - startY);
      panel.style.height = Math.max(35, Math.min(window.innerHeight * 0.7, newHeight)) + 'px';
      if (state.terminalFit) state.terminalFit.fit();
    }

    function onMouseUp() {
      handle.classList.remove('active');
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    }
  }

  // =========================================================================
  // Toolbar Buttons
  // =========================================================================
  document.getElementById('btn-open-folder')?.addEventListener('click', openFolderDialog);
  document.getElementById('btn-run-file')?.addEventListener('click', runCurrentFile);
  document.getElementById('btn-refresh')?.addEventListener('click', refreshFileTree);

  // Refactoring / Analysis buttons (sidebar)
  document.getElementById('btn-refactor-all')?.addEventListener('click', refactorCode);
  document.getElementById('btn-analyze-code')?.addEventListener('click', analyzeCode);
  document.getElementById('btn-check-errors')?.addEventListener('click', checkErrors);

  // Quick action buttons above editor
  document.getElementById('btn-refactor-quick')?.addEventListener('click', refactorCode);
  document.getElementById('btn-analyze-quick')?.addEventListener('click', analyzeCode);
  document.getElementById('btn-check-errors-quick')?.addEventListener('click', checkErrors);
  document.getElementById('btn-push-github')?.addEventListener('click', pushCodeToGitHub);

  // New feature buttons
  document.getElementById('btn-refactor-history')?.addEventListener('click', () => {
    document.querySelector('.activitybar-item[data-panel="history"]')?.click();
    renderRefactoringHistory();
  });
  document.getElementById('btn-rename-symbol')?.addEventListener('click', renameSymbolAcrossFiles);
  document.getElementById('btn-build-dep-graph')?.addEventListener('click', buildDependencyGraph);
  document.getElementById('btn-clear-history')?.addEventListener('click', clearRefactoringHistory);

  // Analysis panel buttons
  document.getElementById('btn-analyze-panel')?.addEventListener('click', analyzeCode);
  document.getElementById('btn-check-errors-panel')?.addEventListener('click', checkErrors);

  // Diff overlay buttons
  document.getElementById('btn-accept-refactor')?.addEventListener('click', acceptRefactoring);
  document.getElementById('btn-reject-refactor')?.addEventListener('click', rejectRefactoring);

  // Graph panel toggle
  document.getElementById('btn-toggle-graph')?.addEventListener('click', () => {
    state.graphExpanded = !state.graphExpanded;
    const wrapper = document.getElementById('graph-canvas-wrapper');
    const btn = document.getElementById('btn-toggle-graph');
    if (wrapper) {
      wrapper.classList.toggle('collapsed', !state.graphExpanded);
      wrapper.classList.toggle('expanded', state.graphExpanded);
    }
    if (btn) btn.textContent = state.graphExpanded ? '▾' : '▸';
  });

  // Keyboard shortcuts for diff overlay
  document.addEventListener('keydown', (e) => {
    if (!state.diffSession) return;
    if (e.key === 'Escape') { rejectRefactoring(); e.preventDefault(); }
    if (e.ctrlKey && e.key === 'Enter') { acceptRefactoring(); e.preventDefault(); }
  });

  // Global keyboard shortcuts — work even when Monaco does NOT have focus
  document.addEventListener('keydown', (e) => {
    // Skip if Monaco editor is focused — it has its own addCommand bindings
    const activeEl = document.activeElement;
    const inMonaco = activeEl && (activeEl.closest('#monaco-container') || activeEl.closest('.monaco-editor'));
    if (inMonaco) return;

    if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === 'o') {
      e.preventDefault(); openFolderDialog();
    } else if (e.ctrlKey && !e.shiftKey && e.key.toLowerCase() === 'o') {
      e.preventDefault(); openFileDialog();
    } else if (e.ctrlKey && !e.shiftKey && e.key.toLowerCase() === 'n') {
      e.preventDefault(); createTab('', '', true);
    } else if (e.ctrlKey && !e.shiftKey && e.key.toLowerCase() === 's') {
      e.preventDefault(); saveFile(state.activeTabId);
    } else if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === 's') {
      e.preventDefault(); saveAsFile();
    } else if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === 'e') {
      e.preventDefault(); document.querySelector('.activitybar-item[data-panel="explorer"]')?.click();
    } else if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === 'f') {
      e.preventDefault(); document.querySelector('.activitybar-item[data-panel="search"]')?.click();
    } else if (e.key === 'F5') {
      e.preventDefault(); runCurrentFile();
    } else if (e.ctrlKey && e.key === '`') {
      e.preventDefault();
      ensurePanelVisible();
      showPanel('terminal-panel');
      state.terminal?.focus();
    }
  });

  document.getElementById('welcome-open-file')?.addEventListener('click', openFileDialog);
  document.getElementById('welcome-open-folder')?.addEventListener('click', openFolderDialog);
  document.getElementById('welcome-new-file')?.addEventListener('click', () => createTab('', '', true));

  // VS Code-style inline input for new file/folder names
  function showInlineInput(placeholder) {
    return new Promise((resolve) => {
      const tree = document.getElementById('file-tree');
      const wrapper = document.createElement('div');
      wrapper.style.cssText = 'padding:2px 8px; display:flex; align-items:center;';
      const input = document.createElement('input');
      input.type = 'text';
      input.placeholder = placeholder;
      input.style.cssText = 'width:100%; background:#3c3c3c; color:#ccc; border:1px solid #007acc; outline:none; padding:2px 6px; font-size:13px; font-family:inherit; border-radius:2px;';
      wrapper.appendChild(input);
      tree.insertBefore(wrapper, tree.firstChild);
      input.focus();

      function finish(value) {
        wrapper.remove();
        resolve(value || null);
      }
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') finish(input.value.trim());
        if (e.key === 'Escape') finish(null);
      });
      input.addEventListener('blur', () => finish(input.value.trim()));
    });
  }

  document.getElementById('btn-new-file')?.addEventListener('click', async () => {
    if (!state.workspacePath) return;
    const name = await showInlineInput('File name...');
    if (name) {
      try {
        const sep = await api.pathSep();
        await api.createFile(state.workspacePath + sep + name);
        refreshFileTree();
      } catch (err) {
        showNotification(err.message || 'Failed to create file', 'error');
      }
    }
  });

  document.getElementById('btn-new-folder')?.addEventListener('click', async () => {
    if (!state.workspacePath) return;
    const name = await showInlineInput('Folder name...');
    if (name) {
      try {
        const sep = await api.pathSep();
        await api.createDir(state.workspacePath + sep + name);
        refreshFileTree();
      } catch (err) {
        showNotification(err.message || 'Failed to create folder', 'error');
      }
    }
  });

  // =========================================================================
  // Menu Event Handlers
  // =========================================================================
  const menuHandlers = {
    'menu:newFile': () => createTab('', '', true),
    'menu:openFile': openFileDialog,
    'menu:openFolder': openFolderDialog,
    'menu:save': () => saveFile(state.activeTabId),
    'menu:saveAs': saveAsFile,
    'menu:autoSave': (checked) => { state.autoSave = checked; },
    'menu:find': () => state.editor?.trigger('menu', 'actions.find', null),
    'menu:replace': () => state.editor?.trigger('menu', 'editor.action.startFindReplaceAction', null),
    'menu:toggleExplorer': () => document.querySelector('.activitybar-item[data-panel="explorer"]')?.click(),
    'menu:toggleSearch': () => document.querySelector('.activitybar-item[data-panel="search"]')?.click(),
    'menu:toggleTerminal': () => {
      ensurePanelVisible();
      showPanel('terminal-panel');
      state.terminal?.focus();
    },
    'menu:toggleOutput': () => {
      ensurePanelVisible();
      showPanel('output-panel');
    },
    'menu:runFile': runCurrentFile,
    'menu:newTerminal': () => document.getElementById('btn-new-terminal')?.click(),
  };

  Object.entries(menuHandlers).forEach(([channel, handler]) => {
    api.onMenuEvent(channel, handler);
  });

  // =========================================================================
  // Utility
  // =========================================================================
  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // =========================================================================
  // CodeNova AI Chat
  // =========================================================================
  const chat = {
    messages: [],        // { role: 'user'|'assistant', content, mode?, newCode?, actions?, dashboard? }
    attachedCode: null,  // string or null
    attachedFile: null,  // file label
    isLoading: false,
  };

  const chatMessagesEl = document.getElementById('chat-messages');
  const chatInput = document.getElementById('chat-input');
  const chatSendBtn = document.getElementById('chat-send-btn');
  const chatContextBar = document.getElementById('chat-context-bar');
  const chatContextFile = document.getElementById('chat-context-file');

  // --- Auto-resize textarea ---
  chatInput.addEventListener('input', () => {
    chatInput.style.height = 'auto';
    chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
    chatSendBtn.disabled = !chatInput.value.trim();
  });

  // --- Send on Enter (Shift+Enter for newline) ---
  chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (chatInput.value.trim() && !chat.isLoading) sendChatMessage();
    }
  });

  chatSendBtn.addEventListener('click', () => {
    if (chatInput.value.trim() && !chat.isLoading) sendChatMessage();
  });

  // --- Attach code from active editor ---
  document.getElementById('chat-attach-code').addEventListener('click', () => {
    const tab = getActiveTab();
    if (!tab) return;
    chat.attachedCode = tab.model.getValue();
    chat.attachedFile = tab.label;
    chatContextBar.style.display = 'flex';
    chatContextFile.textContent = tab.label;
  });

  document.getElementById('chat-context-clear').addEventListener('click', () => {
    chat.attachedCode = null;
    chat.attachedFile = null;
    chatContextBar.style.display = 'none';
  });

  // --- Clear chat ---
  document.getElementById('chat-clear-history').addEventListener('click', () => {
    chat.messages = [];
    chat.attachedCode = null;
    chat.attachedFile = null;
    chatContextBar.style.display = 'none';
    chatMessagesEl.innerHTML = '';
    renderChatWelcome();
  });

  // --- Suggestion buttons ---
  document.querySelectorAll('.chat-suggestion-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const prompt = btn.dataset.prompt;
      // Auto-attach code if a Java file is open
      const tab = getActiveTab();
      if (tab && isJavaFile(tab) && !chat.attachedCode) {
        chat.attachedCode = tab.model.getValue();
        chat.attachedFile = tab.label;
        chatContextBar.style.display = 'flex';
        chatContextFile.textContent = tab.label;
      }
      chatInput.value = prompt;
      chatInput.dispatchEvent(new Event('input'));
      sendChatMessage();
    });
  });

  // --- Keyboard shortcut to open chat: Ctrl+Shift+I ---
  document.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.shiftKey && e.key === 'I') {
      e.preventDefault();
      document.querySelector('.activitybar-item[data-panel="chat"]')?.click();
      setTimeout(() => chatInput.focus(), 100);
    }
  });

  // --- Render welcome ---
  function renderChatWelcome() {
    chatMessagesEl.innerHTML = `
      <div class="chat-welcome">
        <div class="chat-welcome-icon">
          <i class="codicon codicon-comment-discussion"></i>
        </div>
        <h3>CodeNova AI</h3>
        <p>Ask me anything about your Java code \u2014 generate, refactor, or analyze.</p>
        <div class="chat-suggestions">
          <button class="chat-suggestion-btn" data-prompt="Explain this code">Explain this code</button>
          <button class="chat-suggestion-btn" data-prompt="Refactor this code to improve readability">Refactor this code</button>
          <button class="chat-suggestion-btn" data-prompt="Show code health dashboard">Code health</button>
          <button class="chat-suggestion-btn" data-prompt="Find and remove dead code">Remove dead code</button>
        </div>
      </div>
    `;
    // Re-bind suggestion buttons
    chatMessagesEl.querySelectorAll('.chat-suggestion-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const tab = getActiveTab();
        if (tab && isJavaFile(tab) && !chat.attachedCode) {
          chat.attachedCode = tab.model.getValue();
          chat.attachedFile = tab.label;
          chatContextBar.style.display = 'flex';
          chatContextFile.textContent = tab.label;
        }
        chatInput.value = btn.dataset.prompt;
        chatInput.dispatchEvent(new Event('input'));
        sendChatMessage();
      });
    });
  }

  // --- Send message ---
  async function sendChatMessage() {
    const text = chatInput.value.trim();
    if (!text) return;

    // Remove welcome if present
    const welcomeEl = chatMessagesEl.querySelector('.chat-welcome');
    if (welcomeEl) welcomeEl.remove();

    // Add user message
    chat.messages.push({ role: 'user', content: text });
    appendUserBubble(text);

    // Clear input
    chatInput.value = '';
    chatInput.style.height = 'auto';
    chatSendBtn.disabled = true;

    // Show typing indicator
    chat.isLoading = true;
    const typingEl = showTypingIndicator();

    try {
      // Auto-attach current Java code if nothing attached
      let codeToSend = chat.attachedCode;
      if (!codeToSend) {
        const tab = getActiveTab();
        if (tab && isJavaFile(tab)) {
          codeToSend = tab.model.getValue();
        }
      }

      // Retry logic for rate limiting (429)
      let result;
      let retries = 0;
      const maxRetries = 3;
      while (retries <= maxRetries) {
        result = await api.backendChat({
          user_message: text,
          code: codeToSend || undefined,
          file_path: chat.attachedFile || undefined,
        });
        // Check for 429 rate limit
        if (result.detail && (result.detail.includes('429') || result.detail.includes('rate') || result.detail.includes('quota'))) {
          retries++;
          if (retries <= maxRetries) {
            typingEl.querySelector('.typing-text') && (typingEl.querySelector('.typing-text').textContent = `Rate limited, retrying (${retries}/${maxRetries})...`);
            await new Promise(r => setTimeout(r, 2000 * retries));
            continue;
          }
        }
        break;
      }

      typingEl.remove();

      if (result.detail) {
        appendErrorBubble(result.detail);
        return;
      }

      const msg = {
        role: 'assistant',
        content: result.reply,
        mode: result.mode,
        newCode: result.new_code,
        actions: result.refactoring_actions,
        dashboard: result.health_dashboard,
        metrics: result.metrics,
      };
      chat.messages.push(msg);
      appendAssistantBubble(msg);

    } catch (err) {
      typingEl.remove();
      appendErrorBubble(err.message || 'Failed to reach CodeNova AI backend.');
    } finally {
      chat.isLoading = false;
    }
  }

  // --- Render user bubble ---
  function appendUserBubble(text) {
    const el = document.createElement('div');
    el.className = 'chat-message user';
    el.innerHTML = `
      <div class="chat-message-avatar"><i class="codicon codicon-account"></i></div>
      <div class="chat-message-body">
        <div class="chat-message-sender">You</div>
        <div class="chat-message-content">${escapeHtml(text)}</div>
      </div>
    `;
    chatMessagesEl.appendChild(el);
    scrollChatToBottom();
  }

  // --- Render assistant bubble ---
  function appendAssistantBubble(msg) {
    const el = document.createElement('div');
    el.className = 'chat-message assistant';

    const modeBadge = msg.mode
      ? `<span class="chat-mode-badge ${msg.mode}">${msg.mode}</span>`
      : '';

    let bodyHtml = renderMarkdown(msg.content);

    // Refactoring card
    if (msg.mode === 'refactoring' && msg.actions && msg.actions.length > 0) {
      bodyHtml += renderRefactorCard(msg);
    }

    // Health dashboard card
    if (msg.dashboard) {
      bodyHtml += renderHealthCard(msg.dashboard);
    }

    el.innerHTML = `
      <div class="chat-message-avatar"><i class="codicon codicon-comment-discussion"></i></div>
      <div class="chat-message-body">
        <div class="chat-message-sender">CodeNova AI ${modeBadge}</div>
        <div class="chat-message-content">${bodyHtml}</div>
      </div>
    `;

    // Bind code block actions
    el.querySelectorAll('.chat-code-copy').forEach(btn => {
      btn.addEventListener('click', () => {
        const code = btn.closest('.chat-code-block').querySelector('pre').textContent;
        navigator.clipboard.writeText(code);
        btn.innerHTML = '<i class="codicon codicon-check"></i> Copied';
        btn.classList.add('copied');
        setTimeout(() => {
          btn.innerHTML = '<i class="codicon codicon-copy"></i> Copy';
          btn.classList.remove('copied');
        }, 2000);
      });
    });

    el.querySelectorAll('.chat-code-insert').forEach(btn => {
      btn.addEventListener('click', () => {
        const code = btn.closest('.chat-code-block').querySelector('pre').textContent;
        if (state.editor) {
          const model = state.editor.getModel();
          const eol = model ? model.getEOL() : '\n';
          const normalized = code.replace(/\r\n|\r|\n/g, eol);
          const pos = state.editor.getPosition();
          state.editor.executeEdits('chat-insert', [{
            range: new monaco.Range(pos.lineNumber, pos.column, pos.lineNumber, pos.column),
            text: normalized + eol,
            forceMoveMarkers: true,
          }]);
          state.editor.focus();
        }
      });
    });

    // Apply refactored code button
    el.querySelectorAll('.chat-refactor-apply-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        if (msg.newCode && state.editor) {
          const tab = getActiveTab();
          if (tab && tab.model) {
            tab.model.setValue(msg.newCode);
            tab.isDirty = true;
            renderTabs();
            btn.innerHTML = '<i class="codicon codicon-check"></i> Applied!';
            btn.disabled = true;
            btn.style.opacity = '0.6';
          }
        }
      });
    });

    chatMessagesEl.appendChild(el);
    scrollChatToBottom();
  }

  // --- Render error bubble ---
  function appendErrorBubble(message) {
    const el = document.createElement('div');
    el.className = 'chat-error';
    el.innerHTML = `<i class="codicon codicon-error"></i><span>${escapeHtml(message)}</span>`;
    chatMessagesEl.appendChild(el);
    scrollChatToBottom();
  }

  // --- Typing indicator ---
  function showTypingIndicator() {
    const el = document.createElement('div');
    el.className = 'chat-message assistant';
    el.innerHTML = `
      <div class="chat-message-avatar"><i class="codicon codicon-comment-discussion"></i></div>
      <div class="chat-message-body">
        <div class="chat-message-sender">CodeNova AI</div>
        <div class="chat-typing">
          <div class="chat-typing-dot"></div>
          <div class="chat-typing-dot"></div>
          <div class="chat-typing-dot"></div>
        </div>
      </div>
    `;
    chatMessagesEl.appendChild(el);
    scrollChatToBottom();
    return el;
  }

  // --- Simple Markdown → HTML ---
  function renderMarkdown(text) {
    if (!text) return '';
    let html = escapeHtml(text);

    // Normalize line endings so CRLF from the backend doesn't break the regex.
    html = html.replace(/\r\n/g, '\n');

    // Stash code blocks BEFORE other transforms so the `\n` → `<br>` pass
    // below cannot clobber newlines inside <pre>. Restore at the end.
    const codeBlocks = [];
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (match, lang, code) => {
      const placeholder = ` CODEBLOCK${codeBlocks.length} `;
      codeBlocks.push({ lang: lang || 'code', code });
      return placeholder;
    });

    // Inline code: `..`
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Bold: **text**
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

    // Italic: *text*
    html = html.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, '<em>$1</em>');

    // Bullet lists: lines starting with - or *
    html = html.replace(/^[\-\*] (.+)$/gm, '<li>$1</li>');
    html = html.replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>');

    // Paragraphs (double newlines)
    html = html.replace(/\n\n/g, '</p><p>');
    html = html.replace(/\n/g, '<br>');
    html = '<p>' + html + '</p>';
    html = html.replace(/<p><\/p>/g, '');

    // Restore code blocks — newlines inside <pre> are preserved verbatim.
    html = html.replace(/ CODEBLOCK(\d+) /g, (_, idx) => {
      const { lang, code } = codeBlocks[Number(idx)];
      return `<div class="chat-code-block">
        <div class="chat-code-header">
          <span class="chat-code-lang">${lang}</span>
          <div class="chat-code-actions">
            <button class="chat-code-copy"><i class="codicon codicon-copy"></i> Copy</button>
            <button class="chat-code-insert"><i class="codicon codicon-insert"></i> Insert</button>
          </div>
        </div>
        <pre>${code}</pre>
      </div>`;
    });

    return html;
  }

  // --- Refactoring card ---
  function renderRefactorCard(msg) {
    const actionsHtml = (msg.actions || []).slice(0, 8).map(a => {
      const type = a.action_type || a.type || 'refactoring';
      const desc = a.description || a.desc || '';
      return `<div class="chat-refactor-action">
        <span class="action-badge">${escapeHtml(type)}</span>
        <span>${escapeHtml(desc)}</span>
      </div>`;
    }).join('');

    const applyBtn = msg.newCode
      ? `<button class="chat-refactor-apply-btn"><i class="codicon codicon-check"></i> Apply Refactored Code</button>`
      : '';

    return `
      <div class="chat-refactor-card">
        <div class="refactor-card-header">
          <i class="codicon codicon-wand"></i>
          Engine applied ${(msg.actions || []).length} refactoring(s)
        </div>
        <div class="chat-refactor-actions-list">${actionsHtml}</div>
        ${applyBtn}
      </div>
    `;
  }

  // --- Health dashboard card ---
  function renderHealthCard(dashboard) {
    const cat = dashboard.category || 'UNKNOWN';
    const fmt = (v, d) => (typeof v === 'number' ? v.toFixed(d) : '-');

    const healthScore = fmt(dashboard.health_score, 1);
    const mi = fmt(dashboard.maintainability_index, 1);

    let metricsHtml = '';
    metricsHtml += `<div class="chat-health-metric"><span>Health Score</span><span class="metric-val">${healthScore}</span></div>`;
    metricsHtml += `<div class="chat-health-metric"><span>Maintainability</span><span class="metric-val">${mi}</span></div>`;

    if (typeof dashboard.halstead_volume === 'number')
      metricsHtml += `<div class="chat-health-metric"><span>Halstead Vol.</span><span class="metric-val">${fmt(dashboard.halstead_volume, 0)}</span></div>`;
    if (dashboard.complexity != null)
      metricsHtml += `<div class="chat-health-metric"><span>Complexity</span><span class="metric-val">${dashboard.complexity}</span></div>`;
    if (typeof dashboard.coupling === 'number')
      metricsHtml += `<div class="chat-health-metric"><span>Coupling</span><span class="metric-val">${fmt(dashboard.coupling, 2)}</span></div>`;
    if (typeof dashboard.cohesion === 'number')
      metricsHtml += `<div class="chat-health-metric"><span>Cohesion</span><span class="metric-val">${fmt(dashboard.cohesion, 2)}</span></div>`;

    return `
      <div class="chat-health-card">
        <div class="chat-health-header">
          <i class="codicon codicon-pulse"></i>
          Code Health
          <span class="health-category ${cat}">${cat}</span>
        </div>
        <div class="chat-health-metrics">${metricsHtml}</div>
      </div>
    `;
  }

  function scrollChatToBottom() {
    requestAnimationFrame(() => {
      chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
    });
  }

  // =========================================================================
  // Search & Replace Functionality
  // =========================================================================
  const searchInput = document.getElementById('search-input');
  const replaceInput = document.getElementById('replace-input');
  const searchResults = document.getElementById('search-results');
  let searchDebounce = null;

  if (searchInput) {
    searchInput.addEventListener('input', () => {
      clearTimeout(searchDebounce);
      searchDebounce = setTimeout(() => performSearch(), 400);
    });
    searchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') performSearch();
    });
  }

  // Replace on Enter when replace field is focused
  if (replaceInput) {
    replaceInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        performReplaceAll();
      }
    });
  }

  /**
   * Replace all occurrences of search text with replace text across workspace files.
   */
  async function performReplaceAll() {
    const query = searchInput?.value?.trim();
    const replaceText = replaceInput?.value;
    if (!query || replaceText === undefined || replaceText === null) return;
    if (!state.workspacePath) {
      showNotification('Open a folder first to search & replace.', 'error');
      return;
    }

    // Also replace in the current editor if the query matches
    let editorReplacements = 0;
    if (state.editor) {
      const model = state.editor.getModel();
      if (model) {
        const fullText = model.getValue();
        const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const regex = new RegExp(escaped, 'gi');
        const matches = fullText.match(regex);
        if (matches && matches.length > 0) {
          const newText = fullText.replace(regex, replaceText);
          model.setValue(newText);
          const tab = getActiveTab();
          if (tab) { tab.isDirty = true; renderTabs(); }
          editorReplacements = matches.length;
        }
      }
    }

    // Replace in workspace files via backend
    try {
      const results = await api.workspaceSearch({ rootPath: state.workspacePath, query });
      if (results && results.length > 0) {
        const fileSet = new Set(results.map(r => r.filePath));
        let totalFiles = 0;
        let totalReplacements = 0;
        const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const regex = new RegExp(escaped, 'g');

        for (const filePath of fileSet) {
          // Skip the currently open file — already handled above
          const activeTab = getActiveTab();
          if (activeTab && activeTab.filePath === filePath && !activeTab.isUntitled) continue;

          try {
            const content = await api.readFile(filePath);
            const matches = content.match(regex);
            if (matches && matches.length > 0) {
              const newContent = content.replace(regex, replaceText);
              await api.writeFile(filePath, newContent);
              totalFiles++;
              totalReplacements += matches.length;
            }
          } catch (_) {}
        }
        showNotification(
          `Replaced ${totalReplacements + editorReplacements} occurrence(s) in ${totalFiles + (editorReplacements > 0 ? 1 : 0)} file(s).`,
          'info'
        );
      } else if (editorReplacements > 0) {
        showNotification(`Replaced ${editorReplacements} occurrence(s) in current file.`, 'info');
      } else {
        showNotification('No matches found to replace.', 'error');
      }
    } catch (err) {
      showNotification('Replace error: ' + err.message, 'error');
    }

    // Re-run search to update results
    performSearch();
  }

  async function performSearch() {
    const query = searchInput?.value?.trim();
    if (!query || !searchResults) {
      if (searchResults) searchResults.innerHTML = '';
      return;
    }

    // Search in open files if no workspace, or workspace files via IPC
    if (state.workspacePath) {
      searchResults.innerHTML = '<p class="muted" style="padding:8px;">Searching...</p>';
      try {
        const results = await api.workspaceSearch({ rootPath: state.workspacePath, query });
        if (!results || results.length === 0) {
          searchResults.innerHTML = '<p class="muted" style="padding:8px;">No results found.</p>';
          return;
        }
        // Group by file
        const grouped = {};
        for (const r of results) {
          if (!grouped[r.relativePath]) grouped[r.relativePath] = [];
          grouped[r.relativePath].push(r);
        }
        let html = '';
        for (const [relPath, matches] of Object.entries(grouped)) {
          html += `<div class="search-file-group">
            <div class="search-file-header" title="${escapeHtml(matches[0].filePath)}">
              <i class="codicon codicon-file"></i>
              <span>${escapeHtml(relPath)}</span>
              <span class="search-match-count">${matches.length}</span>
            </div>`;
          for (const m of matches) {
            const highlighted = escapeHtml(m.content).replace(
              new RegExp(escapeHtml(query).replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi'),
              match => `<span class="search-highlight">${match}</span>`
            );
            html += `<div class="search-result-item" data-file="${escapeHtml(m.filePath)}" data-line="${m.line}">
              <span class="search-line-num">Ln ${m.line}</span>
              <span class="search-line-content">${highlighted}</span>
            </div>`;
          }
          html += '</div>';
        }
        searchResults.innerHTML = html;

        // Click handlers
        searchResults.querySelectorAll('.search-result-item').forEach(el => {
          el.addEventListener('click', async () => {
            const filePath = el.dataset.file;
            const line = parseInt(el.dataset.line);
            await openFileFromPath(filePath);
            setTimeout(() => {
              if (state.editor && line > 0) {
                state.editor.revealLineInCenter(line);
                state.editor.setPosition({ lineNumber: line, column: 1 });
                state.editor.focus();
              }
            }, 200);
          });
        });
      } catch (err) {
        searchResults.innerHTML = `<p class="muted" style="padding:8px;">Search error: ${escapeHtml(err.message)}</p>`;
      }
    } else {
      searchResults.innerHTML = '<p class="muted" style="padding:8px;">Open a folder first to search.</p>';
    }
  }

  // =========================================================================
  // Source Control (Git) Panel
  // =========================================================================
  const gitState = {
    repoOpen: false,
    staged: [],
    changes: [],
    branches: [],
    currentBranch: '',
    refreshing: false,
  };

  const scmEls = {};
  function scmEl(id) {
    if (!scmEls[id]) scmEls[id] = document.getElementById(id);
    return scmEls[id];
  }

  async function gitRefresh() {
    if (gitState.refreshing || !state.workspacePath || !state.backendReady) return;
    gitState.refreshing = true;
    try {
      const statusRes = await api.gitStatus({ repo_path: state.workspacePath });
      if (statusRes.error || statusRes.detail) {
        gitShowNoRepo(true);
        gitState.repoOpen = false;
        return;
      }
      gitState.repoOpen = true;
      gitShowNoRepo(false);
      gitState.currentBranch = statusRes.branch || '';
      gitState.staged = (statusRes.changes || []).filter(f => f.staged);
      gitState.changes = (statusRes.changes || []).filter(f => !f.staged);
      renderScmFiles();
      await gitRefreshBranches();
      updateBranchStatus();
    } catch (e) {
      gitShowNoRepo(true);
      gitState.repoOpen = false;
    } finally {
      gitState.refreshing = false;
    }
  }

  function gitShowNoRepo(show) {
    const noRepo = scmEl('scm-no-repo');
    const staged = scmEl('scm-staged-section');
    const changes = scmEl('scm-changes-section');
    const inputArea = document.querySelector('.scm-input-area');
    const branchBar = document.querySelector('.scm-branch-bar');
    if (noRepo) noRepo.style.display = show ? 'flex' : 'none';
    if (staged) staged.style.display = show ? 'none' : '';
    if (changes) changes.style.display = show ? 'none' : '';
    if (inputArea) inputArea.style.display = show ? 'none' : '';
    if (branchBar) branchBar.style.display = show ? 'none' : 'flex';
  }

  function renderScmFiles() {
    const stagedList = scmEl('scm-staged-list');
    const changesList = scmEl('scm-changes-list');
    const stagedSection = scmEl('scm-staged-section');
    const stagedCount = scmEl('scm-staged-count');
    const changesCount = scmEl('scm-changes-count');

    if (stagedSection) stagedSection.style.display = gitState.staged.length > 0 ? '' : 'none';
    if (stagedCount) stagedCount.textContent = gitState.staged.length;
    if (changesCount) changesCount.textContent = gitState.changes.length;

    if (stagedList) stagedList.innerHTML = gitState.staged.map(f => scmFileItem(f, true)).join('');
    if (changesList) changesList.innerHTML = gitState.changes.map(f => scmFileItem(f, false)).join('');

    // Bind file item actions
    document.querySelectorAll('.scm-file-item[data-path]').forEach(el => {
      el.querySelectorAll('[data-action]').forEach(btn => {
        btn.addEventListener('click', async (e) => {
          e.stopPropagation();
          const path = el.dataset.path;
          const action = btn.dataset.action;
          if (action === 'stage') await api.gitStage({ repo_path: state.workspacePath, paths: [path] });
          else if (action === 'unstage') await api.gitUnstage({ repo_path: state.workspacePath, paths: [path] });
          else if (action === 'discard') await api.gitDiscard({ repo_path: state.workspacePath, paths: [path] });
          await gitRefresh();
        });
      });
      el.addEventListener('click', async () => {
        try {
          const diff = await api.gitDiff({ repo_path: state.workspacePath, path: el.dataset.path });
          if (diff && diff.diff) {
            appendOutput('[Git Diff] ' + el.dataset.path + '\n' + diff.diff + '\n');
            showPanel('output-panel');
          }
        } catch (_) {}
      });
    });
  }

  function scmFileItem(file, isStaged) {
    const name = file.path.split('/').pop();
    const dir = file.path.includes('/') ? file.path.substring(0, file.path.lastIndexOf('/')) : '';
    const statusChar = (file.status || 'M').charAt(0).toUpperCase();
    const actions = isStaged
      ? `<button data-action="unstage" title="Unstage"><i class="codicon codicon-remove"></i></button>`
      : `<button data-action="stage" title="Stage"><i class="codicon codicon-add"></i></button>
         <button data-action="discard" title="Discard"><i class="codicon codicon-discard"></i></button>`;

    return `<div class="scm-file-item" data-path="${file.path}">
      <span class="scm-file-status ${statusChar}">${statusChar}</span>
      <span class="scm-file-name">${name}</span>
      ${dir ? `<span class="scm-file-path">${dir}</span>` : ''}
      <span class="scm-file-actions">${actions}</span>
    </div>`;
  }

  async function gitRefreshBranches() {
    try {
      const res = await api.gitBranches({ repo_path: state.workspacePath });
      if (res && res.local) {
        const current = res.current || '';
        gitState.currentBranch = current;
        gitState.branches = res.local.map(name => ({ name, is_current: name === current }));
        const sel = scmEl('scm-branch-select');
        if (sel) {
          sel.innerHTML = gitState.branches.map(b =>
            `<option value="${b.name}" ${b.is_current ? 'selected' : ''}>${b.name}${b.is_current ? ' *' : ''}</option>`
          ).join('');
        }
      }
    } catch (_) {}
  }

  function updateBranchStatus() {
    const el = document.getElementById('status-branch');
    if (el && gitState.currentBranch) {
      el.innerHTML = `<i class="codicon codicon-git-branch"></i> ${gitState.currentBranch}`;
    }
  }

  // Bind SCM UI events after DOM is ready
  function initScmBindings() {
    // Commit
    const commitBtn = scmEl('scm-commit-btn');
    const commitMsg = scmEl('scm-commit-msg');
    if (commitBtn && commitMsg) {
      commitBtn.addEventListener('click', async () => {
        const msg = commitMsg.value.trim();
        if (!msg) return;
        const res = await api.gitCommit({ repo_path: state.workspacePath, message: msg });
        if (res && !res.error) {
          commitMsg.value = '';
          appendOutput('[Git] Committed: ' + (res.hash || '').substring(0, 7) + ' ' + msg + '\n');
        } else {
          appendOutput('[Git Error] ' + (res.error || 'Commit failed') + '\n');
        }
        await gitRefresh();
      });
      commitMsg.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key === 'Enter') commitBtn.click();
      });
    }

    // Refresh
    const refreshBtn = scmEl('scm-refresh-btn');
    if (refreshBtn) refreshBtn.addEventListener('click', () => gitRefresh());

    // Stage all
    const stageAllBtn = scmEl('scm-stage-all-btn');
    if (stageAllBtn) stageAllBtn.addEventListener('click', async () => {
      await api.gitStageAll({ repo_path: state.workspacePath });
      await gitRefresh();
    });

    // Unstage all
    const unstageAllBtn = scmEl('scm-unstage-all-btn');
    if (unstageAllBtn) unstageAllBtn.addEventListener('click', async () => {
      const paths = gitState.staged.map(f => f.path);
      if (paths.length) await api.gitUnstage({ repo_path: state.workspacePath, paths });
      await gitRefresh();
    });

    // Discard all
    const discardAllBtn = scmEl('scm-discard-all-btn');
    if (discardAllBtn) discardAllBtn.addEventListener('click', async () => {
      const paths = gitState.changes.map(f => f.path);
      if (paths.length) await api.gitDiscard({ repo_path: state.workspacePath, paths });
      await gitRefresh();
    });

    // Push / Pull
    const pushBtn = scmEl('scm-push-btn');
    if (pushBtn) pushBtn.addEventListener('click', async () => {
      const res = await api.gitPush({ repo_path: state.workspacePath });
      appendOutput('[Git] ' + (res.error ? 'Push error: ' + res.error : 'Pushed successfully') + '\n');
    });

    const pullBtn = scmEl('scm-pull-btn');
    if (pullBtn) pullBtn.addEventListener('click', async () => {
      const res = await api.gitPull({ repo_path: state.workspacePath });
      appendOutput('[Git] ' + (res.error ? 'Pull error: ' + res.error : 'Pulled successfully') + '\n');
      await gitRefresh();
    });

    // Stash
    const stashBtn = scmEl('scm-stash-btn');
    if (stashBtn) stashBtn.addEventListener('click', async () => {
      const res = await api.gitStashSave({ repo_path: state.workspacePath });
      appendOutput('[Git] ' + (res.error ? 'Stash error: ' + res.error : 'Changes stashed') + '\n');
      await gitRefresh();
    });

    // Branch switching
    const branchSel = scmEl('scm-branch-select');
    if (branchSel) branchSel.addEventListener('change', async () => {
      const name = branchSel.value;
      if (name) {
        const res = await api.gitBranchSwitch({ repo_path: state.workspacePath, name });
        if (res && !res.error) {
          appendOutput('[Git] Switched to branch: ' + name + '\n');
        } else {
          appendOutput('[Git Error] ' + (res.error || 'Switch failed') + '\n');
        }
        await gitRefresh();
      }
    });

    // New branch
    const newBranchBtn = scmEl('scm-branch-new-btn');
    if (newBranchBtn) newBranchBtn.addEventListener('click', async () => {
      const name = prompt('New branch name:');
      if (name && name.trim()) {
        const res = await api.gitBranchCreate({ repo_path: state.workspacePath, name: name.trim() });
        if (res && !res.error) {
          appendOutput('[Git] Created branch: ' + name.trim() + '\n');
        } else {
          appendOutput('[Git Error] ' + (res.error || 'Branch creation failed') + '\n');
        }
        await gitRefresh();
      }
    });

    // Init repo
    const initBtn = scmEl('scm-init-btn');
    if (initBtn) initBtn.addEventListener('click', async () => {
      const res = await api.gitInit({ repo_path: state.workspacePath });
      if (res && !res.error) {
        appendOutput('[Git] Repository initialized\n');
        await gitRefresh();
      } else {
        appendOutput('[Git Error] ' + (res.error || 'Init failed') + '\n');
      }
    });
  }

  // =========================================================================
  // Multi-File Dependency Graph
  // =========================================================================
  async function buildDependencyGraph() {
    if (!state.workspacePath) {
      showNotification('Open a folder first to build dependency graph.', 'error');
      return;
    }
    if (!state.backendReady) {
      showNotification('Backend is not running.', 'error');
      return;
    }

    const emptyState = document.getElementById('dep-graph-empty');
    const canvas = document.getElementById('dep-graph-canvas');
    if (emptyState) emptyState.innerHTML = '<p class="muted">Building dependency graph...</p>';

    try {
      const files = await api.readJavaFiles(state.workspacePath);
      if (!files || Object.keys(files).length === 0) {
        if (emptyState) {
          emptyState.style.display = 'flex';
          emptyState.innerHTML = '<i class="codicon codicon-type-hierarchy" style="font-size:48px;opacity:0.3;"></i><p>No Java files found in this folder.</p>';
        }
        return;
      }

      const result = await api.multiFileDependencyGraph({ files });
      if (result.detail) {
        showNotification('Error: ' + result.detail, 'error');
        return;
      }

      if (!result.nodes || result.nodes.length === 0) {
        if (emptyState) {
          emptyState.style.display = 'flex';
          emptyState.innerHTML = '<i class="codicon codicon-type-hierarchy" style="font-size:48px;opacity:0.3;"></i><p>No dependencies found.</p>';
        }
        return;
      }

      if (emptyState) emptyState.style.display = 'none';
      drawDependencyGraph(canvas, result.nodes, result.edges || []);
    } catch (err) {
      showNotification('Dependency graph error: ' + (err.message || 'Unknown'), 'error');
    }
  }

  function drawDependencyGraph(canvas, nodes, edges) {
    const container = canvas.parentElement;
    const rect = container.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const minH = Math.max(nodes.length * 55, 500);
    const w = Math.max(rect.width, 400);
    const h = Math.max(rect.height, minH);
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = w + 'px';
    canvas.style.height = h + 'px';
    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, w, h);

    if (nodes.length === 0) return;

    // ── Hierarchical layout: rank nodes by dependency depth ──
    const nodeKey = (n) => n.id || n.file || n.label;
    const nodeLabel = (n) => {
      const s = n.label || n.file || n.id || '';
      return s.split(/[\\/]/).pop().replace('.java', '');
    };

    // Count outgoing edges (dependencies) per node
    const outCount = {};
    const inCount = {};
    nodes.forEach(n => { outCount[nodeKey(n)] = 0; inCount[nodeKey(n)] = 0; });
    edges.forEach(e => {
      const src = e.source || e.from;
      const tgt = e.target || e.to;
      outCount[src] = (outCount[src] || 0) + 1;
      inCount[tgt] = (inCount[tgt] || 0) + 1;
    });

    // Assign layers: BFS from leaf nodes (0 outgoing) upward
    const keySet = new Set(nodes.map(nodeKey));
    const adjOut = {};
    const adjIn = {};
    nodes.forEach(n => { adjOut[nodeKey(n)] = []; adjIn[nodeKey(n)] = []; });
    edges.forEach(e => {
      const src = e.source || e.from;
      const tgt = e.target || e.to;
      if (keySet.has(src) && keySet.has(tgt)) {
        adjOut[src].push(tgt);
        adjIn[tgt].push(src);
      }
    });

    // Topological layer assignment
    const layer = {};
    const visited = new Set();

    function assignLayer(key) {
      if (visited.has(key)) return layer[key] || 0;
      visited.add(key);
      const deps = adjOut[key] || [];
      if (deps.length === 0) {
        layer[key] = 0;
        return 0;
      }
      let maxChild = 0;
      deps.forEach(d => { maxChild = Math.max(maxChild, assignLayer(d)); });
      layer[key] = maxChild + 1;
      return layer[key];
    }
    nodes.forEach(n => assignLayer(nodeKey(n)));

    // Group nodes by layer
    const layers = {};
    nodes.forEach(n => {
      const l = layer[nodeKey(n)] || 0;
      if (!layers[l]) layers[l] = [];
      layers[l].push(n);
    });

    const maxLayer = Math.max(...Object.keys(layers).map(Number));

    // Position nodes with row WRAPPING: a layer with more files than fit
    // across the panel is split into multiple visual rows. Previously all
    // unconnected files shared layer 0 and were squeezed into one row,
    // overlapping into an unreadable stack.
    const padX = 40;
    const padY = 50;
    const NODE_W = 130;
    const H_GAP = 24;
    const V_GAP = 84;
    const usableW = w - padX * 2;
    const perRow = Math.max(1, Math.floor((usableW + H_GAP) / (NODE_W + H_GAP)));

    // Visual rows, top (most-dependent layer) → bottom (leaves).
    const visualRows = [];
    for (let l = maxLayer; l >= 0; l--) {
      const row = layers[l] || [];
      for (let i = 0; i < row.length; i += perRow) {
        visualRows.push(row.slice(i, i + perRow));
      }
    }

    // Resize canvas height to fit all rows (must happen before drawing).
    const neededH = padY * 2 + visualRows.length * V_GAP;
    if (neededH > h) {
      canvas.height = neededH * dpr;
      canvas.style.height = neededH + 'px';
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.scale(dpr, dpr);
      ctx.clearRect(0, 0, w, neededH);
    }

    const nodePositions = {};
    visualRows.forEach((row, r) => {
      const y = padY + r * V_GAP + V_GAP / 2;
      const rowWidth = row.length * NODE_W + (row.length - 1) * H_GAP;
      const startX = padX + Math.max(0, (usableW - rowWidth) / 2) + NODE_W / 2;
      row.forEach((n, i) => {
        nodePositions[nodeKey(n)] = {
          x: startX + i * (NODE_W + H_GAP),
          y: y,
          node: n
        };
      });
    });

    // ── Edge colors & styles ──
    const edgeColors = { extends: '#e53935', implements: '#43a047', uses: '#546e7a' };
    const edgeAlpha = { extends: 1.0, implements: 1.0, uses: 0.45 };

    // ── Draw curved edges ──
    edges.forEach(edge => {
      const fromKey = edge.source || edge.from;
      const toKey = edge.target || edge.to;
      const from = nodePositions[fromKey];
      const to = nodePositions[toKey];
      if (!from || !to) return;

      const color = edgeColors[edge.type] || '#546e7a';
      const alpha = edgeAlpha[edge.type] || 0.45;
      ctx.save();
      ctx.globalAlpha = alpha;

      // Curved line (quadratic bezier with offset control point)
      const cpX = (from.x + to.x) / 2 + (from.y - to.y) * 0.15;
      const cpY = (from.y + to.y) / 2;

      ctx.beginPath();
      ctx.moveTo(from.x, from.y);
      ctx.quadraticCurveTo(cpX, cpY, to.x, to.y);
      ctx.strokeStyle = color;
      ctx.lineWidth = edge.type === 'extends' ? 2.5 : edge.type === 'implements' ? 2 : 1.2;
      if (edge.type === 'implements') ctx.setLineDash([5, 3]);
      else ctx.setLineDash([]);
      ctx.stroke();
      ctx.setLineDash([]);

      // Arrow head near target
      const t = 0.92;
      const ax = (1 - t) * (1 - t) * from.x + 2 * (1 - t) * t * cpX + t * t * to.x;
      const ay = (1 - t) * (1 - t) * from.y + 2 * (1 - t) * t * cpY + t * t * to.y;
      const tx = 2 * (1 - t) * (cpX - from.x) + 2 * t * (to.x - cpX);
      const ty = 2 * (1 - t) * (cpY - from.y) + 2 * t * (to.y - cpY);
      const ang = Math.atan2(ty, tx);
      const aLen = 8;
      ctx.globalAlpha = Math.min(alpha + 0.3, 1.0);
      ctx.beginPath();
      ctx.moveTo(ax, ay);
      ctx.lineTo(ax - aLen * Math.cos(ang - 0.35), ay - aLen * Math.sin(ang - 0.35));
      ctx.lineTo(ax - aLen * Math.cos(ang + 0.35), ay - aLen * Math.sin(ang + 0.35));
      ctx.closePath();
      ctx.fillStyle = color;
      ctx.fill();

      ctx.restore();
    });

    // ── Draw nodes ──
    ctx.font = '12px "Segoe UI", "Cascadia Code", monospace';
    const nodeW = 130;
    const nodeH = 34;

    // Color nodes by role
    const nodeColors = {};
    nodes.forEach(n => {
      const k = nodeKey(n);
      const out = outCount[k] || 0;
      const inc = inCount[k] || 0;
      if (out === 0 && inc > 0)      nodeColors[k] = { bg: '#1b3a2a', border: '#4caf50', text: '#a5d6a7' }; // leaf model (green)
      else if (out >= 4)             nodeColors[k] = { bg: '#3e1929', border: '#e53935', text: '#ef9a9a' }; // hub/entry (red)
      else if (out >= 2)             nodeColors[k] = { bg: '#1a2a3e', border: '#42a5f5', text: '#90caf9' }; // service (blue)
      else                           nodeColors[k] = { bg: '#2d2d2d', border: '#78909c', text: '#cfd8dc' }; // default (grey)
    });

    nodes.forEach(n => {
      const k = nodeKey(n);
      const pos = nodePositions[k];
      if (!pos) return;

      const label = nodeLabel(n);
      const colors = nodeColors[k];
      const tw = ctx.measureText(label).width;
      const nw = Math.max(tw + 28, nodeW);

      // Shadow
      ctx.save();
      ctx.shadowColor = 'rgba(0,0,0,0.4)';
      ctx.shadowBlur = 8;
      ctx.shadowOffsetY = 2;

      // Rounded rect
      ctx.fillStyle = colors.bg;
      ctx.beginPath();
      ctx.roundRect(pos.x - nw / 2, pos.y - nodeH / 2, nw, nodeH, 8);
      ctx.fill();
      ctx.restore();

      // Border
      ctx.strokeStyle = colors.border;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.roundRect(pos.x - nw / 2, pos.y - nodeH / 2, nw, nodeH, 8);
      ctx.stroke();

      // Label
      ctx.fillStyle = colors.text;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(label, pos.x, pos.y);

      // Small badge showing edge counts
      const badge = (inCount[k] || 0) + ' in / ' + (outCount[k] || 0) + ' out';
      ctx.font = '9px "Segoe UI", sans-serif';
      ctx.fillStyle = 'rgba(255,255,255,0.3)';
      ctx.fillText(badge, pos.x, pos.y + nodeH / 2 + 10);
      ctx.font = '12px "Segoe UI", "Cascadia Code", monospace';
    });

    // ── Legend ──
    const legendY = h - 30;
    const legendItems = [
      { color: '#4caf50', border: '#1b3a2a', label: 'Model (leaf)' },
      { color: '#42a5f5', border: '#1a2a3e', label: 'Service' },
      { color: '#e53935', border: '#3e1929', label: 'Hub / Entry' },
    ];
    ctx.font = '10px "Segoe UI", sans-serif';
    let lx = 12;
    legendItems.forEach(item => {
      ctx.fillStyle = item.color;
      ctx.fillRect(lx, legendY, 10, 10);
      ctx.fillStyle = '#999';
      ctx.textAlign = 'left';
      ctx.textBaseline = 'middle';
      ctx.fillText(item.label, lx + 14, legendY + 5);
      lx += ctx.measureText(item.label).width + 28;
    });

    // Edge legend
    lx += 10;
    const edgeLegend = [
      { color: '#e53935', dash: [], label: 'extends' },
      { color: '#43a047', dash: [5, 3], label: 'implements' },
      { color: '#546e7a', dash: [], label: 'uses' },
    ];
    edgeLegend.forEach(item => {
      ctx.strokeStyle = item.color;
      ctx.lineWidth = 2;
      ctx.setLineDash(item.dash);
      ctx.beginPath();
      ctx.moveTo(lx, legendY + 5);
      ctx.lineTo(lx + 16, legendY + 5);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = '#999';
      ctx.fillText(item.label, lx + 20, legendY + 5);
      lx += ctx.measureText(item.label).width + 36;
    });
  }

  // =========================================================================
  // Refactoring History
  // =========================================================================
  async function renderRefactoringHistory() {
    const container = document.getElementById('history-list');
    if (!container) return;

    try {
      const result = await api.getRefactoringHistory();
      const history = result.history || result || [];

      if (!Array.isArray(history) || history.length === 0) {
        container.innerHTML = '<p class="muted" style="padding:8px;">No refactoring history yet.</p>';
        return;
      }

      container.innerHTML = history.reverse().map((entry, i) => {
        const date = entry.timestamp ? new Date(entry.timestamp).toLocaleString() : 'Unknown time';
        const fileName = (entry.file_path || '').split(/[\\/]/).pop() || 'Unknown file';
        const actionsCount = (entry.actions || []).length;
        return `
          <div class="history-item" data-index="${i}" style="padding:8px;border-bottom:1px solid var(--border);cursor:pointer;">
            <div style="display:flex;justify-content:space-between;align-items:center;">
              <span style="color:#e0e0e0;font-size:12px;font-weight:600;">${escapeHtml(fileName)}</span>
              <span style="color:var(--text-muted);font-size:10px;">${escapeHtml(date)}</span>
            </div>
            <div style="color:var(--text-secondary);font-size:11px;margin-top:2px;">
              ${actionsCount} action(s) applied
            </div>
            ${(entry.actions || []).slice(0, 3).map(a => `
              <div style="color:var(--text-muted);font-size:10px;margin-top:1px;">
                • ${escapeHtml(a.action_type || a.description || 'refactoring')}
              </div>
            `).join('')}
          </div>
        `;
      }).join('');

      // Click to view diff of history entry
      container.querySelectorAll('.history-item').forEach(el => {
        el.addEventListener('click', () => {
          const idx = parseInt(el.dataset.index);
          const entry = history[idx];
          if (entry && entry.original_code && entry.refactored_code) {
            showDiffOverlayReadOnly(entry.original_code, entry.refactored_code, entry.file_path);
          }
        });
      });
    } catch (err) {
      container.innerHTML = '<p class="muted" style="padding:8px;">Failed to load history.</p>';
    }
  }

  function showDiffOverlayReadOnly(originalCode, modifiedCode, title) {
    const overlay = document.getElementById('diff-overlay');
    const diffContainer = document.getElementById('diff-editor-container');
    const summary = document.getElementById('diff-summary');
    const acceptBtn = document.getElementById('btn-accept-refactor');
    const rejectBtn = document.getElementById('btn-reject-refactor');

    summary.textContent = (title || 'History').split(/[\\/]/).pop();
    overlay.style.display = 'flex';

    // Hide accept button for read-only history view
    if (acceptBtn) acceptBtn.style.display = 'none';
    if (rejectBtn) rejectBtn.textContent = ' Close';

    if (diffEditorInstance) {
      diffEditorInstance.dispose();
      diffEditorInstance = null;
    }

    setTimeout(() => {
      diffEditorInstance = monaco.editor.createDiffEditor(diffContainer, {
        theme: 'codenova-dark',
        readOnly: true,
        automaticLayout: true,
        renderSideBySide: true,
        fontSize: 13,
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
      });

      diffEditorInstance.setModel({
        original: monaco.editor.createModel(originalCode, 'java'),
        modified: monaco.editor.createModel(modifiedCode, 'java'),
      });
    }, 50);

    // Restore accept button on close
    const origHide = hideDiffOverlay;
    const tempHide = () => {
      if (acceptBtn) acceptBtn.style.display = '';
      if (rejectBtn) rejectBtn.innerHTML = '<i class="codicon codicon-close"></i> Reject';
      origHide();
    };
    document.getElementById('btn-reject-refactor').onclick = tempHide;
  }

  async function clearRefactoringHistory() {
    try {
      await api.clearRefactoringHistory();
      showNotification('Refactoring history cleared.', 'info');
      renderRefactoringHistory();
    } catch (err) {
      showNotification('Failed to clear history.', 'error');
    }
  }

  // Save history entry after accepting refactoring
  const originalAcceptRefactoring = acceptRefactoring;

  // =========================================================================
  // Rename Symbol Across Files
  // =========================================================================
  async function renameSymbolAcrossFiles() {
    if (!state.workspacePath) {
      showNotification('Open a folder first.', 'error');
      return;
    }
    if (!state.backendReady) {
      showNotification('Backend is not running.', 'error');
      return;
    }

    // Get selected text as default old name
    let defaultOldName = '';
    if (state.editor) {
      const selection = state.editor.getSelection();
      if (selection && !selection.isEmpty()) {
        defaultOldName = state.editor.getModel().getValueInRange(selection);
      }
    }

    // Show rename modal
    const result = await showRenameModal(defaultOldName);
    if (!result) return;

    const { oldName, newName } = result;
    if (!oldName || !newName || oldName === newName) {
      showNotification('Invalid rename: names must be different.', 'error');
      return;
    }

    try {
      const res = await api.renameSymbol({
        root_path: state.workspacePath,
        old_name: oldName,
        new_name: newName
      });

      if (res.detail) {
        showNotification('Rename error: ' + res.detail, 'error');
        return;
      }

      const count = res.count || 0;
      const modifiedFiles = res.modified_files || [];
      showNotification(`Renamed "${oldName}" → "${newName}" in ${count} file(s).`, 'info');

      // Reload open tabs that were modified
      for (const mf of modifiedFiles) {
        const openTab = state.openTabs.find(t => t.filePath && t.filePath.replace(/\\/g, '/').endsWith(mf.relative_path.replace(/\\/g, '/')));
        if (openTab) {
          try {
            const content = await api.readFile(openTab.filePath);
            openTab.model.setValue(content);
            openTab.isDirty = false;
          } catch (_) {}
        }
      }
      renderTabs();
    } catch (err) {
      showNotification('Rename failed: ' + (err.message || 'Unknown error'), 'error');
    }
  }

  function showRenameModal(defaultOldName) {
    return new Promise((resolve) => {
      const overlay = document.createElement('div');
      overlay.className = 'github-modal-overlay';
      overlay.innerHTML = `
        <div class="github-modal">
          <div class="github-modal-header">
            <i class="codicon codicon-symbol-key"></i>
            Rename Symbol Across Files
          </div>
          <div class="github-modal-body">
            <div>
              <label>Current Name</label>
              <input type="text" id="rename-old-name" placeholder="e.g. calculateTotal" value="${escapeHtml(defaultOldName || '')}" spellcheck="false" />
            </div>
            <div>
              <label>New Name</label>
              <input type="text" id="rename-new-name" placeholder="e.g. computeTotal" spellcheck="false" />
            </div>
          </div>
          <div class="github-modal-footer">
            <button class="github-btn-cancel" id="rename-cancel-btn">Cancel</button>
            <button class="github-btn-push" id="rename-apply-btn">
              <i class="codicon codicon-symbol-key"></i> Rename
            </button>
          </div>
        </div>
      `;
      document.body.appendChild(overlay);

      const oldInput = overlay.querySelector('#rename-old-name');
      const newInput = overlay.querySelector('#rename-new-name');
      const applyBtn = overlay.querySelector('#rename-apply-btn');
      const cancelBtn = overlay.querySelector('#rename-cancel-btn');

      if (defaultOldName) newInput.focus(); else oldInput.focus();

      function cleanup() { overlay.remove(); }

      cancelBtn.addEventListener('click', () => { cleanup(); resolve(null); });
      overlay.addEventListener('click', (e) => {
        if (e.target === overlay) { cleanup(); resolve(null); }
      });

      function onKey(e) {
        if (e.key === 'Escape') { document.removeEventListener('keydown', onKey); cleanup(); resolve(null); }
        if (e.key === 'Enter') { applyBtn.click(); }
      }
      document.addEventListener('keydown', onKey);

      applyBtn.addEventListener('click', () => {
        document.removeEventListener('keydown', onKey);
        const oldName = oldInput.value.trim();
        const newName = newInput.value.trim();
        cleanup();
        resolve({ oldName, newName });
      });
    });
  }

  // =========================================================================
  // Push Code to GitHub
  // =========================================================================

  /**
   * Get the localStorage key for a project's GitHub repo URL.
   */
  function getRepoUrlKey(projectPath) {
    return 'github_repo_url::' + projectPath.replace(/[\\/]/g, '/').toLowerCase();
  }

  /**
   * Show the Push-to-GitHub modal dialog and return user input.
   * Resolves with { repoUrl, commitMessage } or null if cancelled.
   */
  function showGitHubPushModal(savedUrl) {
    return new Promise((resolve) => {
      // Build modal DOM
      const overlay = document.createElement('div');
      overlay.className = 'github-modal-overlay';
      overlay.innerHTML = `
        <div class="github-modal">
          <div class="github-modal-header">
            <i class="codicon codicon-cloud-upload"></i>
            Push Code to GitHub
          </div>
          <div class="github-modal-body">
            <div>
              <label>Repository URL</label>
              <input type="text" id="github-repo-url" placeholder="https://github.com/user/repo.git" value="${escapeHtml(savedUrl || '')}" spellcheck="false" />
            </div>
            <div>
              <label>GitHub Account</label>
              <div id="github-signin-row" style="display:none;gap:8px;align-items:center;margin-bottom:6px">
                <button id="github-signin-btn" style="display:flex;align-items:center;gap:6px"><i class="codicon codicon-github"></i> Sign in with GitHub</button>
                <span id="github-signin-status" style="font-size:12px;opacity:.8"></span>
              </div>
              <label style="font-size:11px;opacity:.7">Personal Access Token — create one at github.com/settings/tokens (scope: repo)</label>
              <input type="password" id="github-token" placeholder="ghp_…" spellcheck="false" autocomplete="off" />
            </div>
            <div>
              <label>Commit Message</label>
              <input type="text" id="github-commit-msg" placeholder="Update from CodeNova IDE" spellcheck="false" />
            </div>
            <label style="display:flex;align-items:center;gap:6px;font-size:12px;opacity:.85">
              <input type="checkbox" id="github-remember-token" />
              Remember this token for this project (stored in localStorage, plaintext)
            </label>
          </div>
          <div class="github-modal-footer">
            <button class="github-btn-cancel" id="github-cancel-btn">Cancel</button>
            <button class="github-btn-push" id="github-push-btn">
              <i class="codicon codicon-cloud-upload"></i> Push
            </button>
          </div>
        </div>
      `;
      document.body.appendChild(overlay);

      const urlInput = overlay.querySelector('#github-repo-url');
      const tokenInput = overlay.querySelector('#github-token');
      const rememberToken = overlay.querySelector('#github-remember-token');
      const msgInput = overlay.querySelector('#github-commit-msg');
      const pushBtn = overlay.querySelector('#github-push-btn');
      const cancelBtn = overlay.querySelector('#github-cancel-btn');

      // OAuth sign-in row is shown only when a Client ID has been configured
      // (Settings → Set GitHub OAuth Client ID). Default UX is PAT-only.
      if (localStorage.getItem('github.oauthClientId')) {
        overlay.querySelector('#github-signin-row').style.display = 'flex';
      }
      // Pre-fill token: prefer a GitHub sign-in token, else a remembered PAT.
      const oauthToken = localStorage.getItem('github.oauthToken') || '';
      const oauthLogin = localStorage.getItem('github.oauthLogin') || '';
      const savedToken = localStorage.getItem(getRepoUrlKey(state.workspacePath || '') + ':token') || '';
      const statusEl = overlay.querySelector('#github-signin-status');
      if (oauthToken) {
        tokenInput.value = oauthToken;
        statusEl.textContent = `Signed in as ${oauthLogin || 'GitHub user'} ✓`;
      } else if (savedToken) {
        tokenInput.value = savedToken;
        rememberToken.checked = true;
      }

      // Device-flow sign-in: show the code, open the browser, wait for grant.
      overlay.querySelector('#github-signin-btn').addEventListener('click', async () => {
        const btn = overlay.querySelector('#github-signin-btn');
        btn.disabled = true;
        statusEl.textContent = 'Contacting GitHub…';
        try {
          const clientId = localStorage.getItem('github.oauthClientId') || '';
          const start = await api.githubDeviceStart({ clientId });
          if (start.error) { statusEl.textContent = start.error; btn.disabled = false; return; }
          statusEl.innerHTML = `Enter code <b style="font-family:monospace">${escapeHtml(start.user_code)}</b> in the browser…`;
          api.openExternal(start.verification_uri);
          const result = await api.githubDeviceWait({ device_code: start.device_code, interval: start.interval, clientId: start._client_id });
          if (result.error) { statusEl.textContent = result.error; btn.disabled = false; return; }
          localStorage.setItem('github.oauthToken', result.token);
          if (result.login) localStorage.setItem('github.oauthLogin', result.login);
          tokenInput.value = result.token;
          statusEl.textContent = `Signed in as ${result.login || 'GitHub user'} ✓`;
        } catch (e) {
          statusEl.textContent = 'Sign-in failed: ' + e.message;
          btn.disabled = false;
        }
      });

      // Focus the right field
      if (savedUrl && !savedToken) { tokenInput.focus(); }
      else if (savedUrl) { msgInput.focus(); }
      else { urlInput.focus(); }

      function cleanup() { overlay.remove(); }

      cancelBtn.addEventListener('click', () => { cleanup(); resolve(null); });
      overlay.addEventListener('click', (e) => {
        if (e.target === overlay) { cleanup(); resolve(null); }
      });

      function onKey(e) {
        if (e.key === 'Escape') { document.removeEventListener('keydown', onKey); cleanup(); resolve(null); }
        if (e.key === 'Enter' && e.target !== msgInput) { pushBtn.click(); }
      }
      document.addEventListener('keydown', onKey);

      pushBtn.addEventListener('click', () => {
        document.removeEventListener('keydown', onKey);
        const repoUrl = urlInput.value.trim();
        const token = tokenInput.value.trim();
        const commitMessage = msgInput.value.trim() || 'Update from CodeNova IDE';
        const remember = rememberToken.checked;
        cleanup();
        resolve({ repoUrl, token, commitMessage, remember });
      });
    });
  }

  /**
   * Main push-to-GitHub workflow triggered by the toolbar button.
   * Auto-pushes when a repo URL is already saved for this project.
   */
  async function pushCodeToGitHub() {
    // Determine the project path
    const projectPath = state.workspacePath;
    if (!projectPath) {
      showNotification('Open a folder first before pushing to GitHub.', 'error');
      return;
    }

    // Check localStorage for a saved repo URL + (optionally remembered) token.
    const storageKey = getRepoUrlKey(projectPath);
    const tokenKey = storageKey + ':token';
    const savedUrl = localStorage.getItem(storageKey) || '';
    // OAuth sign-in token (global, from "Sign in with GitHub") takes priority
    // over a per-project remembered PAT.
    const savedToken = localStorage.getItem('github.oauthToken') || localStorage.getItem(tokenKey) || '';

    let repoUrl, commitMessage, token;

    if (savedUrl && savedToken) {
      // Fully silent auto-push: URL + token already known.
      repoUrl = savedUrl;
      token = savedToken;
      commitMessage = 'Update from CodeNova IDE — ' + new Date().toLocaleString();
    } else {
      // Need user input — show modal (pre-fills with whatever we have).
      const input = await showGitHubPushModal(savedUrl);
      if (!input) return; // User cancelled
      repoUrl = input.repoUrl;
      token = input.token;
      commitMessage = input.commitMessage;

      if (repoUrl) localStorage.setItem(storageKey, repoUrl);
      if (input.remember && token) {
        localStorage.setItem(tokenKey, token);
      } else {
        localStorage.removeItem(tokenKey);
      }
    }

    // Show a progress notification
    const progressEl = document.createElement('div');
    progressEl.style.cssText = 'position:fixed;top:12px;right:12px;z-index:10000;padding:10px 18px;border-radius:4px;font-size:13px;color:#fff;max-width:400px;box-shadow:0 4px 12px rgba(0,0,0,.4);background:#007acc;';
    progressEl.innerHTML = '<span class="github-modal-spinner"></span> Pushing to GitHub...';
    document.body.appendChild(progressEl);

    try {
      const result = await api.pushToGitHub({
        projectPath,
        repoUrl,
        commitMessage,
        token,
        githubLogin: localStorage.getItem('github.oauthLogin') || '',
      });

      progressEl.remove();

      if (result && result.success) {
        showNotification(`Pushed to origin/${result.branch || 'main'} successfully!`, 'info');
        appendOutput('[GitHub Push] ' + (result.message || 'Success') + '\n');
        if (result.steps) {
          result.steps.forEach(s => appendOutput('  • ' + s + '\n'));
        }
      } else {
        const errMsg = (result && result.error) || 'Unknown error';
        showNotification('Push failed: ' + errMsg, 'error');
        appendOutput('[GitHub Push Error] ' + errMsg + '\n');
      }
    } catch (err) {
      progressEl.remove();
      showNotification('Push failed: ' + (err.message || err), 'error');
      appendOutput('[GitHub Push Error] ' + (err.message || err) + '\n');
    }

    // Refresh git status in the source control panel
    setTimeout(() => gitRefresh(), 500);
  }

  // Hook into panel switch to auto-refresh git and history
  const origActivityClickSetup = () => {
    document.querySelectorAll('.activitybar-item[data-panel]').forEach(btn => {
      btn.addEventListener('click', () => {
        if (btn.dataset.panel === 'source-control') {
          setTimeout(() => gitRefresh(), 100);
        }
        if (btn.dataset.panel === 'history') {
          setTimeout(() => renderRefactoringHistory(), 100);
        }
      });
    });
  };

  // =========================================================================
  // Real-time Collaboration
  // =========================================================================

  // Production relay (deployed on Render) — every installed copy uses this
  // by default; users can override from the 📡 menu if they self-host.
  const COLLAB_RELAY_DEFAULT = localStorage.getItem('collab.relayUrl') || 'wss://codenova-relay.onrender.com';

  function getUsername() {
    let n = localStorage.getItem('collab.username');
    if (!n) {
      n = `User-${Math.random().toString(36).slice(2, 6)}`;
      localStorage.setItem('collab.username', n);
    }
    return n;
  }

  function initCollabIfPresent() {
    if (!window.collab) {
      console.warn('[collab] client.js not loaded; collaboration disabled');
      return false;
    }
    window.collab.init({
      relayUrl: COLLAB_RELAY_DEFAULT,
      monacoInstance: window.monaco,
      username: getUsername(),
    });
    window.collab.onPresence(renderPresenceBadge);
    return true;
  }

  function renderPresenceBadge(peers) {
    let el = document.getElementById('collab-presence');
    if (!el) {
      el = document.createElement('div');
      el.id = 'collab-presence';
      el.style.cssText = 'position:fixed;top:6px;right:12px;z-index:9000;display:flex;gap:4px;align-items:center;font-size:11px;color:#ddd;background:#252526;padding:3px 8px;border-radius:12px;box-shadow:0 1px 4px rgba(0,0,0,.4)';
      document.body.appendChild(el);
    }
    if (!peers || peers.length === 0) {
      el.style.display = 'none';
      return;
    }
    el.style.display = 'flex';
    el.innerHTML = peers.map((p) =>
      `<span title="${escapeHtml(p.name)}" style="display:inline-flex;align-items:center;gap:4px"><span style="width:8px;height:8px;border-radius:50%;background:${p.color}"></span>${escapeHtml(p.name)}</span>`
    ).join(' · ');
  }

  function showShareModal() {
    if (!initCollabIfPresent()) return;
    const overlay = document.createElement('div');
    overlay.className = 'github-modal-overlay';
    overlay.innerHTML = `
      <div class="github-modal">
        <div class="github-modal-header"><i class="codicon codicon-broadcast"></i> Share Workspace</div>
        <div class="github-modal-body">
          <label>How should teammates connect?</label>
          <select id="collab-mode" style="width:100%;padding:6px;background:#3c3c3c;color:#fff;border:1px solid #555;margin-bottom:8px">
            <option value="lan" selected>Same network (instant — your app hosts, no server)</option>
            <option value="relay">Worldwide (via relay server — works from anywhere)</option>
          </select>
          <div id="collab-mode-hint" style="font-size:12px;opacity:.7;margin-bottom:8px">
            Your CodeNova becomes the session host. Works for teammates on the
            same Wi-Fi/LAN; the session ends when you close the app.
          </div>
          <div id="collab-token-result" style="display:none;margin-top:12px">
            <label>Join token — send this to your teammate</label>
            <textarea id="collab-token-text" readonly style="width:100%;height:74px;background:#1e1e1e;color:#9cdcfe;border:1px solid #555;padding:6px;font-family:Menlo,monospace;font-size:11px"></textarea>
            <button id="collab-copy-token" style="margin-top:6px"><i class="codicon codicon-copy"></i> Copy</button>
          </div>
        </div>
        <div class="github-modal-footer">
          <button class="github-btn-cancel" id="collab-cancel">Close</button>
          <button class="github-btn-push" id="collab-generate"><i class="codicon codicon-broadcast"></i> Start Sharing</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    const close = () => overlay.remove();
    overlay.querySelector('#collab-cancel').onclick = close;

    const modeSel = overlay.querySelector('#collab-mode');
    const hintEl = overlay.querySelector('#collab-mode-hint');
    modeSel.onchange = () => {
      hintEl.innerHTML = modeSel.value === 'lan'
        ? 'Your CodeNova becomes the session host. Works for teammates on the same Wi-Fi/LAN; the session ends when you close the app.'
        : `Uses the relay server (<b>${escapeHtml(localStorage.getItem('collab.relayUrl') || COLLAB_RELAY_DEFAULT)}</b>). Teammates can join from anywhere in the world. Configure the relay URL from the 📡 menu.`;
    };

    overlay.querySelector('#collab-generate').onclick = async () => {
      const btn = overlay.querySelector('#collab-generate');
      btn.disabled = true;
      try {
        let shareToken;
        if (modeSel.value === 'lan') {
          // In-app host (idempotent — reuses a running session).
          const info = await api.collabHostStart();
          if (info.error) throw new Error(info.error);
          await window.collab.joinDirect(info.localUrl, info.workspaceId, info.key);
          shareToken = btoa(JSON.stringify({ u: info.url, w: info.workspaceId, k: info.key }));
          showNotification('Live session started — you are hosting.', 'info');
        } else {
          // Worldwide: JWT session on the configured relay server.
          try {
            const { token, workspaceId } = await window.collab.shareWorkspace({ role: 'editor' });
            shareToken = token;
            showNotification(`Worldwide session ${workspaceId.slice(0, 8)}… started.`, 'info');
          } catch (relayErr) {
            throw new Error(
              'Relay server unreachable at ' +
              (localStorage.getItem('collab.relayUrl') || COLLAB_RELAY_DEFAULT) +
              '. Deploy collab-server (see repo README) and set its URL via the 📡 menu → "Collab Server". (' + relayErr.message + ')');
          }
        }
        overlay.querySelector('#collab-token-text').value = shareToken;
        overlay.querySelector('#collab-token-result').style.display = 'block';
      } catch (e) {
        showNotification('Share failed: ' + e.message, 'error');
        btn.disabled = false;
      }
    };
    overlay.querySelector('#collab-copy-token').onclick = () => {
      const ta = overlay.querySelector('#collab-token-text');
      ta.select();
      document.execCommand('copy');
      showNotification('Token copied.', 'info');
    };
  }

  function showJoinModal() {
    if (!initCollabIfPresent()) return;
    const overlay = document.createElement('div');
    overlay.className = 'github-modal-overlay';
    overlay.innerHTML = `
      <div class="github-modal">
        <div class="github-modal-header"><i class="codicon codicon-link"></i> Join Workspace</div>
        <div class="github-modal-body">
          <div>
            <label>Join token</label>
            <textarea id="collab-join-token" placeholder="Paste token from your supervisor / teammate" style="width:100%;height:74px;background:#1e1e1e;color:#fff;border:1px solid #555;padding:6px;font-family:Menlo,monospace;font-size:11px"></textarea>
          </div>
          <div style="margin-top:8px">
            <label>Display name (others will see this on cursors)</label>
            <input type="text" id="collab-display-name" value="${escapeHtml(getUsername())}" style="width:100%;padding:6px;background:#3c3c3c;color:#fff;border:1px solid #555" />
          </div>
        </div>
        <div class="github-modal-footer">
          <button class="github-btn-cancel" id="collab-cancel">Cancel</button>
          <button class="github-btn-push" id="collab-join-go"><i class="codicon codicon-link"></i> Join</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    const close = () => overlay.remove();
    overlay.querySelector('#collab-cancel').onclick = close;
    overlay.querySelector('#collab-join-go').onclick = async () => {
      try {
        const name = overlay.querySelector('#collab-display-name').value.trim() || getUsername();
        localStorage.setItem('collab.username', name);
        window.collab.init({
          relayUrl: COLLAB_RELAY_DEFAULT,
          monacoInstance: window.monaco,
          username: name,
        });
        window.collab.onPresence(renderPresenceBadge);
        const token = overlay.querySelector('#collab-join-token').value.trim();
        if (!token) return;

        // New self-contained tokens are base64 JSON {u: hostUrl, w, k}.
        // Fall back to legacy JWT tokens (external relay) if parsing fails.
        let direct = null;
        try {
          const parsed = JSON.parse(atob(token));
          if (parsed.u && parsed.w && parsed.k) direct = parsed;
        } catch (_) {}

        let workspaceId, role;
        if (direct) {
          ({ workspaceId, role } = await window.collab.joinDirect(direct.u, direct.w, direct.k));
        } else {
          ({ workspaceId, role } = await window.collab.joinWithToken(token));
        }
        showNotification(`Joined workspace ${workspaceId.slice(0, 8)}… as ${role}.`, 'info');
        close();
      } catch (e) {
        showNotification('Join failed: ' + e.message, 'error');
      }
    };
  }

  // Public hooks for the activity bar / command palette.
  window.codenovaCollab = {
    share: showShareModal,
    join: showJoinModal,
    bindActiveTab: (tab) => {
      if (window.collab && window.collab.isConnected() && tab && tab.path) {
        const unbind = window.collab.bindEditor(state.editor, tab.path);
        tab._collabUnbind = unbind;
      }
    },
    unbindTab: (tab) => {
      if (tab && tab._collabUnbind) {
        tab._collabUnbind();
        tab._collabUnbind = null;
      }
    },
  };

  // Optional: wire to buttons if present in the DOM.
  document.getElementById('btn-collab-share')?.addEventListener('click', showShareModal);
  document.getElementById('btn-collab-join')?.addEventListener('click', showJoinModal);

  // ---- Activity-bar popup menus (Collab + Settings) ----

  function showPopupMenu(anchorEl, items) {
    document.getElementById('activitybar-popup')?.remove();
    const menu = document.createElement('div');
    menu.id = 'activitybar-popup';
    const rect = anchorEl.getBoundingClientRect();
    menu.style.cssText = `position:fixed;left:${rect.right + 6}px;bottom:${window.innerHeight - rect.bottom}px;z-index:10001;background:#252526;border:1px solid #454545;border-radius:5px;min-width:230px;padding:4px 0;box-shadow:0 4px 14px rgba(0,0,0,.5);font-size:13px;color:#ddd`;
    for (const item of items) {
      if (item === '---') {
        const sep = document.createElement('div');
        sep.style.cssText = 'height:1px;background:#454545;margin:4px 8px';
        menu.appendChild(sep);
        continue;
      }
      const row = document.createElement('div');
      row.style.cssText = 'padding:6px 14px;cursor:pointer;display:flex;align-items:center;gap:8px';
      row.innerHTML = `<i class="codicon codicon-${item.icon}"></i><span>${escapeHtml(item.label)}</span>`;
      row.addEventListener('mouseenter', () => row.style.background = '#094771');
      row.addEventListener('mouseleave', () => row.style.background = '');
      row.addEventListener('click', () => { menu.remove(); item.action(); });
      menu.appendChild(row);
    }
    document.body.appendChild(menu);
    const dismiss = (e) => {
      if (!menu.contains(e.target)) { menu.remove(); document.removeEventListener('mousedown', dismiss); }
    };
    setTimeout(() => document.addEventListener('mousedown', dismiss), 0);
  }

  document.getElementById('btn-collab-menu')?.addEventListener('click', (e) => {
    const connected = window.collab && window.collab.isConnected();
    showPopupMenu(e.currentTarget, [
      { icon: 'broadcast', label: 'Share Workspace (start live session)', action: showShareModal },
      { icon: 'link', label: 'Join Workspace (paste token)', action: showJoinModal },
      '---',
      { icon: 'server', label: `Collab Server: ${COLLAB_RELAY_DEFAULT}`, action: () => {
        const url = prompt('Collaboration relay URL (ws:// or wss://):', COLLAB_RELAY_DEFAULT);
        if (url) { localStorage.setItem('collab.relayUrl', url.trim()); showNotification('Relay URL saved. Rejoin your workspace to apply.', 'info'); }
      }},
      ...(connected ? [{ icon: 'debug-disconnect', label: 'Leave / stop session', action: () => {
        window.collab.disconnect();
        api.collabHostStop?.();
        showNotification('Live session ended.', 'info');
        renderPresenceBadge([]);
      }}] : []),
    ]);
  });

  document.getElementById('btn-settings')?.addEventListener('click', (e) => {
    // VS Code-style Manage menu. No API keys, no publisher knobs — those are
    // baked into the build. (Backend /config endpoints still exist for
    // power users via curl, but nothing in the UI surfaces them.)
    showPopupMenu(e.currentTarget, [
      { icon: 'account', label: `Accounts: ${localStorage.getItem('github.oauthLogin') || getUsername()}`, action: () => {
        const n = prompt('Display name (shown to teammates in live sessions):', getUsername());
        if (n && n.trim()) { localStorage.setItem('collab.username', n.trim()); showNotification('Name saved.', 'info'); }
      }},
      '---',
      { icon: 'coffee', label: 'Set Java (JDK) location…', action: async () => {
        const r = await api.javaLocate?.();
        if (!r || r.canceled) return;
        if (r.error) { showNotification(r.error, 'error'); return; }
        if (r.found) showNotification('JDK set: ' + r.home + '. Open a new terminal to use javac.', 'info');
      }},
      '---',
      { icon: 'settings-gear', label: 'Settings', action: showSettingsPage },
      { icon: 'keyboard', label: 'Keyboard Shortcuts', action: showKeybindingsPage },
      { icon: 'trash', label: 'Clear Saved Data (tokens, repo URLs)', action: () => {
        Object.keys(localStorage).filter(k => k.startsWith('github_repo_url::') || k === 'github.oauthToken' || k === 'github.oauthLogin').forEach(k => localStorage.removeItem(k));
        showNotification('Saved GitHub data cleared.', 'info');
      }},
      '---',
      { icon: 'pulse', label: 'Backend Status', action: async () => {
        const h = await api.backendHealth();
        state.backendReady = h && h.status === 'healthy';
        showNotification(state.backendReady ? 'All systems running.' : 'Backend unavailable: ' + (h.error || ''), state.backendReady ? 'info' : 'error');
      }},
      { icon: 'info', label: 'About CodeNova IDE', action: () => {
        showNotification('CodeNova IDE v2.0.0 — AI-driven Java refactoring IDE. Built with Electron + Monaco.', 'info');
      }},
    ]);
  });

  // =========================================================================
  // JDK detection toast (VS Code-style, actionable)
  // =========================================================================

  api.onJavaStatus?.((s) => {
    if (s.found) return;
    const snoozed = parseInt(localStorage.getItem('jdk.toast.snoozeUntil') || '0');
    if (Date.now() < snoozed) return;
    showJdkToast(s.jreOnly);
  });

  function showJdkToast(jreOnly) {
    document.getElementById('jdk-toast')?.remove();
    // JRE-only is the most common confusion: `java` works but `javac` (the
    // compiler) is missing. Say exactly that instead of a vague "not found".
    const headline = jreOnly ? 'Java compiler (JDK) not found' : 'Java (JDK) not found';
    const body = jreOnly
      ? 'You have the Java <b>runtime</b> (JRE) installed, but compiling and running Java needs the <b>JDK</b> — which includes <code>javac</code>. Install a JDK, or point CodeNova at one you already have.'
      : 'To compile and run Java, CodeNova needs a JDK. Editing, refactoring, and AI chat work without it.';

    const toast = document.createElement('div');
    toast.id = 'jdk-toast';
    toast.style.cssText = 'position:fixed;right:16px;bottom:44px;z-index:10002;width:400px;background:#252526;border:1px solid #454545;border-left:3px solid #cca700;border-radius:6px;padding:16px;box-shadow:0 8px 24px rgba(0,0,0,.55);font-size:13px;color:#ddd';
    toast.innerHTML = `
      <div style="display:flex;gap:10px">
        <i class="codicon codicon-warning" style="color:#cca700;font-size:16px;margin-top:1px"></i>
        <div style="flex:1">
          <div style="font-weight:600;margin-bottom:5px">${headline}</div>
          <div style="color:#9a9a9a;line-height:1.5">${body}</div>
          <div style="display:flex;gap:8px;margin-top:14px;flex-wrap:wrap">
            <button id="jdk-locate" style="background:#0e639c;color:#fff;border:none;padding:6px 12px;border-radius:3px;cursor:pointer"><i class="codicon codicon-folder-opened" style="vertical-align:-2px"></i> Locate my JDK</button>
            <button id="jdk-download" style="background:#3c3c3c;color:#ddd;border:none;padding:6px 12px;border-radius:3px;cursor:pointer">Download JDK</button>
            <button id="jdk-recheck" style="background:#3c3c3c;color:#ddd;border:none;padding:6px 12px;border-radius:3px;cursor:pointer">Re-check</button>
          </div>
        </div>
        <i id="jdk-close" class="codicon codicon-close" style="cursor:pointer;color:#888"></i>
      </div>`;
    document.body.appendChild(toast);
    const dismiss = (snoozeDays) => {
      if (snoozeDays) localStorage.setItem('jdk.toast.snoozeUntil', String(Date.now() + snoozeDays * 864e5));
      toast.remove();
    };
    toast.querySelector('#jdk-download').onclick = () => { api.openExternal('https://adoptium.net/temurin/releases/?version=21'); };
    toast.querySelector('#jdk-close').onclick = () => dismiss(3);
    toast.querySelector('#jdk-locate').onclick = async () => {
      const r = await api.javaLocate();
      if (r.canceled) return;
      if (r.error) { showNotification(r.error, 'error'); return; }
      if (r.found) { showNotification('JDK set: ' + r.home + '. Open a new terminal to use javac.', 'info'); dismiss(0); }
    };
    toast.querySelector('#jdk-recheck').onclick = async () => {
      const r = await api.javaRedetect();
      if (r.found) { showNotification('JDK found: ' + r.home, 'info'); dismiss(0); }
      else { showNotification('Still no JDK detected. Use "Locate my JDK" to point at it.', 'error'); }
    };
  }
  // Expose for the Settings menu.
  window.__jdkToast = showJdkToast;

  // =========================================================================
  // Settings & Keyboard Shortcuts pages (VS Code-style full overlays)
  // =========================================================================

  const SETTINGS_DEFAULTS = { fontSize: 14, tabSize: 4, wordWrap: false, minimap: true, autoSave: false };

  function getUserSettings() {
    try { return { ...SETTINGS_DEFAULTS, ...JSON.parse(localStorage.getItem('user.settings') || '{}') }; }
    catch { return { ...SETTINGS_DEFAULTS }; }
  }

  function saveUserSettings(s) {
    localStorage.setItem('user.settings', JSON.stringify(s));
    applyUserSettings();
  }

  function applyUserSettings() {
    const s = getUserSettings();
    if (state.editor) {
      state.editor.updateOptions({
        fontSize: s.fontSize,
        wordWrap: s.wordWrap ? 'on' : 'off',
        minimap: { enabled: s.minimap },
      });
    }
    state.openTabs.forEach(t => t.model && t.model.updateOptions({ tabSize: s.tabSize }));
    state.autoSave = s.autoSave;
  }

  function closeFullPage() { document.getElementById('full-page-overlay')?.remove(); }

  function openFullPage(title, bodyBuilder) {
    closeFullPage();
    const page = document.createElement('div');
    page.id = 'full-page-overlay';
    page.style.cssText = 'position:absolute;inset:0;z-index:900;background:#1e1e1e;display:flex;flex-direction:column;overflow:hidden';
    page.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;padding:14px 26px;border-bottom:1px solid #333">
        <span style="font-size:20px;font-weight:600;color:#e7e7e7">${escapeHtml(title)}</span>
        <button id="full-page-close" style="background:none;border:none;color:#bbb;cursor:pointer;font-size:16px"><i class="codicon codicon-close"></i></button>
      </div>
      <div id="full-page-body" style="flex:1;overflow-y:auto;padding:18px 26px"></div>`;
    // Mount inside the editor area so the sidebar/activity bar stay usable.
    const host = document.getElementById('monaco-container')?.parentElement || document.body;
    host.style.position = 'relative';
    host.appendChild(page);
    page.querySelector('#full-page-close').onclick = closeFullPage;
    const esc = (ev) => { if (ev.key === 'Escape') { closeFullPage(); document.removeEventListener('keydown', esc); } };
    document.addEventListener('keydown', esc);
    bodyBuilder(page.querySelector('#full-page-body'));
  }

  function showSettingsPage() {
    openFullPage('Settings', (body) => {
      const s = getUserSettings();
      const row = (label, desc, controlHtml) => `
        <div class="settings-row" data-label="${escapeHtml(label.toLowerCase())}" style="padding:14px 0;border-bottom:1px solid #2a2a2a;max-width:720px">
          <div style="font-size:13px;font-weight:600;color:#e7e7e7">${escapeHtml(label)}</div>
          <div style="font-size:12px;color:#9a9a9a;margin:3px 0 8px">${escapeHtml(desc)}</div>
          ${controlHtml}
        </div>`;
      const num = (id, val, min, max) =>
        `<input type="number" id="${id}" value="${val}" min="${min}" max="${max}" style="width:80px;background:#3c3c3c;color:#fff;border:1px solid #555;padding:4px 8px;border-radius:2px">`;
      const chk = (id, val) =>
        `<input type="checkbox" id="${id}" ${val ? 'checked' : ''} style="transform:scale(1.2)">`;

      body.innerHTML = `
        <input id="settings-search" placeholder="Search settings" style="width:100%;max-width:720px;padding:8px 12px;background:#3c3c3c;color:#fff;border:1px solid #555;border-radius:2px;margin-bottom:6px">
        <div style="font-size:11px;letter-spacing:1px;color:#888;margin:18px 0 4px">TEXT EDITOR</div>
        ${row('Font Size', 'Controls the editor font size in pixels.', num('set-fontsize', s.fontSize, 8, 40))}
        ${row('Tab Size', 'The number of spaces a tab is equal to.', num('set-tabsize', s.tabSize, 1, 8))}
        ${row('Word Wrap', 'Wrap long lines instead of horizontal scrolling.', chk('set-wordwrap', s.wordWrap))}
        ${row('Minimap', 'Show the code minimap on the right side of the editor.', chk('set-minimap', s.minimap))}
        <div style="font-size:11px;letter-spacing:1px;color:#888;margin:18px 0 4px">FILES</div>
        ${row('Auto Save', 'Automatically save files one second after you stop typing.', chk('set-autosave', s.autoSave))}
        <div style="font-size:11px;letter-spacing:1px;color:#888;margin:18px 0 4px">COLLABORATION</div>
        ${row('Display Name', 'Shown to teammates on your cursor in live sessions.',
          `<input id="set-displayname" value="${escapeHtml(getUsername())}" style="width:240px;background:#3c3c3c;color:#fff;border:1px solid #555;padding:4px 8px;border-radius:2px">`)}
      `;

      const commit = () => {
        const next = {
          fontSize: parseInt(body.querySelector('#set-fontsize').value) || 14,
          tabSize: parseInt(body.querySelector('#set-tabsize').value) || 4,
          wordWrap: body.querySelector('#set-wordwrap').checked,
          minimap: body.querySelector('#set-minimap').checked,
          autoSave: body.querySelector('#set-autosave').checked,
        };
        saveUserSettings(next);
        const dn = body.querySelector('#set-displayname').value.trim();
        if (dn) localStorage.setItem('collab.username', dn);
      };
      body.querySelectorAll('input').forEach(el => el.addEventListener('change', commit));

      body.querySelector('#settings-search').addEventListener('input', (ev) => {
        const q = ev.target.value.toLowerCase();
        body.querySelectorAll('.settings-row').forEach(r => {
          r.style.display = r.dataset.label.includes(q) ? '' : 'none';
        });
      });
    });
  }

  function showKeybindingsPage() {
    openFullPage('Keyboard Shortcuts', (body) => {
      const isMac = navigator.platform.toUpperCase().includes('MAC');
      const mod = isMac ? '⌘' : 'Ctrl';
      const rows = [
        ['New File', `${mod}+N`], ['Open File', `${mod}+O`], ['Open Folder', `${mod}+K ${mod}+O`],
        ['Save', `${mod}+S`], ['Save As', `${mod}+Shift+S`],
        ['Find', `${mod}+F`], ['Replace', `${mod}+H`],
        ['Toggle Explorer', `${mod}+Shift+E`], ['Search in Files', `${mod}+Shift+F`],
        ['Toggle Terminal', `${mod}+\``], ['New Terminal', `${mod}+Shift+\``],
        ['Run File', 'F5'], ['Stop Run', 'Shift+F5'],
        ['AI Chat', `${mod}+Shift+I`], ['Refactoring Panel', `${mod}+Shift+R`],
        ['Zoom In / Out', `${mod}+= / ${mod}+-`],
        ...(isMac ? [['Quit', '⌘+Q'], ['Hide Window', '⌘+H'], ['Minimize', '⌘+M']] : []),
      ];
      body.innerHTML = `
        <table style="width:100%;max-width:640px;border-collapse:collapse;font-size:13px">
          <tr style="color:#888;text-align:left"><th style="padding:8px;border-bottom:1px solid #333">Command</th><th style="padding:8px;border-bottom:1px solid #333">Keybinding</th></tr>
          ${rows.map(([c, k]) => `<tr><td style="padding:8px;border-bottom:1px solid #2a2a2a;color:#ddd">${escapeHtml(c)}</td><td style="padding:8px;border-bottom:1px solid #2a2a2a"><code style="background:#333;padding:2px 8px;border-radius:3px;color:#9cdcfe">${escapeHtml(k)}</code></td></tr>`).join('')}
        </table>`;
    });
  }

  // =========================================================================
  // Initialize
  // =========================================================================
  async function init() {
    await initMonaco();
    // Apply persisted user settings (font size, wrap, minimap, auto save).
    applyUserSettings();
    // Delay terminal init to let layout settle
    setTimeout(() => initTerminal(), 300);
    // Check backend health after a short delay for startup
    setTimeout(() => checkBackendHealth(), 2000);
    // Init SCM bindings
    initScmBindings();
    origActivityClickSetup();
  }

  init();

})();
