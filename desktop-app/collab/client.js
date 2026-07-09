/* =============================================================================
 * CodeNova IDE — Collaboration client.
 *
 * Wraps Y.js + y-websocket + y-monaco into a small facade the renderer can
 * call from a couple of places without leaking the protocol details.
 *
 * Public API (exposed on window.collab):
 *   collab.init({ relayUrl, monacoInstance })
 *   collab.joinWithToken(token)         → { workspaceId, role }
 *   collab.shareWorkspace(opts)         → { token, workspaceId, joinCode }
 *   collab.bindEditor(editor, filePath) → unbind()
 *   collab.listFiles()                  → [{ path, lastEdit }]
 *   collab.updateFileEntry(path, meta)
 *   collab.deleteFileEntry(path)
 *   collab.onPresence(callback)         → unsubscribe()
 *   collab.onFileTreeChange(callback)   → unsubscribe()
 *   collab.isConnected()
 *   collab.disconnect()
 *
 * The renderer is responsible for:
 *   - Showing the Share / Join modals (renderer.js)
 *   - Calling bindEditor() when a tab opens and unbind() when it closes
 *   - Calling updateFileEntry/deleteFileEntry on local file operations
 *
 * All Y.Doc-level conflict resolution is handled by Y.js itself.
 * ===========================================================================*/

import * as Y from 'yjs';
import { WebsocketProvider } from 'y-websocket';
import { MonacoBinding } from 'y-monaco';

const state = {
  relayUrl: null,
  monacoInstance: null,
  workspaceId: null,
  token: null,
  role: null,
  username: null,
  color: null,
  // The workspace meta doc — file tree only.
  workspaceDoc: null,
  workspaceProvider: null,
  // path → { doc, provider, binding }
  fileBindings: new Map(),
  presenceListeners: new Set(),
  treeListeners: new Set(),
};

// ── Utilities ──────────────────────────────────────────────────────────────

const PALETTE = ['#ff5e5e', '#5ec8ff', '#5eff8b', '#ffb35e', '#c45eff', '#5effe2', '#ff5ed1', '#d4ff5e'];

function pickColor(seed) {
  let hash = 0;
  for (let i = 0; i < seed.length; i++) hash = (hash * 31 + seed.charCodeAt(i)) | 0;
  return PALETTE[Math.abs(hash) % PALETTE.length];
}

function relayHttp(path) {
  // Convert wss:// → https:// and ws:// → http:// for the REST mint endpoint.
  return state.relayUrl.replace(/^wss:/, 'https:').replace(/^ws:/, 'http:') + path;
}

function wsBase() {
  return state.relayUrl.replace(/\/+$/, '');
}

// ── Public API ─────────────────────────────────────────────────────────────

function init({ relayUrl, monacoInstance, username }) {
  state.relayUrl = relayUrl;
  state.monacoInstance = monacoInstance;
  state.username = username || `User-${Math.random().toString(36).slice(2, 6)}`;
  state.color = pickColor(state.username);
}

async function shareWorkspace({ ttlHours = 168, role = 'editor' } = {}) {
  const res = await fetch(relayHttp('/token'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ttl_hours: ttlHours, role }),
  });
  if (!res.ok) throw new Error(`Relay returned ${res.status}`);
  const data = await res.json();
  // Connect locally as owner of the new workspace.
  await _connectWorkspace(data.token, data.workspace_id);
  return {
    token: data.token,
    workspaceId: data.workspace_id,
    joinCode: data.token.slice(-12),
  };
}

/**
 * Connect to an embedded (in-app) host session.
 * `wsBase` e.g. ws://192.168.1.5:53211 — User 1's machine on the LAN.
 */
async function joinDirect(wsBase, workspaceId, key) {
  const httpBase = wsBase.replace(/^wss:/, 'https:').replace(/^ws:/, 'http:');
  let verified = false;
  try {
    const res = await fetch(httpBase + '/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workspace_id: workspaceId, key }),
    });
    verified = res.ok && (await res.json()).valid;
  } catch (e) {
    throw new Error(
      'Cannot reach the host. Make sure the person sharing still has CodeNova open ' +
      'and you are on the same network. (' + e.message + ')');
  }
  if (!verified) throw new Error('Invalid or expired share token.');
  state.relayUrl = wsBase;
  await _connectWorkspace(key, workspaceId, 'editor');
  return { workspaceId, role: 'editor' };
}

async function joinWithToken(token) {
  const verify = await fetch(relayHttp('/verify'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token }),
  });
  if (!verify.ok) throw new Error('Relay unreachable');
  const verifyJson = await verify.json();
  if (!verifyJson.valid) throw new Error(`Invalid or expired token: ${verifyJson.error || 'unknown'}`);
  const { workspace_id, role } = verifyJson.payload;
  await _connectWorkspace(token, workspace_id, role);
  return { workspaceId: workspace_id, role };
}

async function _connectWorkspace(token, workspaceId, role = null) {
  // If a previous workspace was open, close it cleanly first.
  if (state.workspaceProvider) disconnect();

  state.token = token;
  state.workspaceId = workspaceId;
  state.role = role;

  // Workspace meta doc holds the file tree as a Y.Map.
  state.workspaceDoc = new Y.Doc();
  state.workspaceProvider = new WebsocketProvider(
    wsBase(),
    `ws/${workspaceId}`,
    state.workspaceDoc,
    { params: { token, doc: workspaceId } },
  );

  state.workspaceProvider.awareness.setLocalStateField('user', {
    name: state.username,
    color: state.color,
  });

  state.workspaceProvider.awareness.on('change', () => {
    const peers = Array.from(state.workspaceProvider.awareness.getStates().values())
      .map((s) => s.user)
      .filter(Boolean);
    state.presenceListeners.forEach((cb) => { try { cb(peers); } catch (_) {} });
  });

  const files = state.workspaceDoc.getMap('files');
  files.observe(() => {
    state.treeListeners.forEach((cb) => { try { cb(listFiles()); } catch (_) {} });
  });
}

function bindEditor(editor, filePath) {
  if (!state.workspaceId) {
    console.warn('[collab] bindEditor called before workspace is open');
    return () => {};
  }
  if (state.fileBindings.has(filePath)) {
    // Already bound — return the existing unbind.
    return () => unbindEditor(filePath);
  }

  const fileDocName = `${state.workspaceId}/${encodeURIComponent(filePath)}`;
  const ydoc = new Y.Doc();
  const provider = new WebsocketProvider(
    wsBase(),
    `ws/${state.workspaceId}`,
    ydoc,
    { params: { token: state.token, doc: fileDocName } },
  );
  provider.awareness.setLocalStateField('user', {
    name: state.username,
    color: state.color,
  });

  const ytext = ydoc.getText('content');

  // Seed from the editor's current value the first time we sync, if the
  // remote doc is empty. The handshake fires once on initial sync.
  let seeded = false;
  provider.on('sync', (isSynced) => {
    if (!isSynced || seeded) return;
    seeded = true;
    if (ytext.length === 0 && editor.getValue().length > 0) {
      ytext.insert(0, editor.getValue());
    }
  });

  const binding = new MonacoBinding(
    ytext,
    editor.getModel(),
    new Set([editor]),
    provider.awareness,
  );

  state.fileBindings.set(filePath, { ydoc, provider, binding });
  return () => unbindEditor(filePath);
}

function unbindEditor(filePath) {
  const entry = state.fileBindings.get(filePath);
  if (!entry) return;
  try { entry.binding.destroy(); } catch (_) {}
  try { entry.provider.destroy(); } catch (_) {}
  try { entry.ydoc.destroy(); } catch (_) {}
  state.fileBindings.delete(filePath);
}

function listFiles() {
  if (!state.workspaceDoc) return [];
  const files = state.workspaceDoc.getMap('files');
  const out = [];
  files.forEach((meta, path) => {
    out.push({ path, ...meta });
  });
  return out.sort((a, b) => a.path.localeCompare(b.path));
}

function updateFileEntry(filePath, meta = {}) {
  if (!state.workspaceDoc) return;
  state.workspaceDoc.getMap('files').set(filePath, {
    lastEdit: Date.now(),
    editor: state.username,
    ...meta,
  });
}

function deleteFileEntry(filePath) {
  if (!state.workspaceDoc) return;
  state.workspaceDoc.getMap('files').delete(filePath);
}

function onPresence(cb) {
  state.presenceListeners.add(cb);
  return () => state.presenceListeners.delete(cb);
}

function onFileTreeChange(cb) {
  state.treeListeners.add(cb);
  return () => state.treeListeners.delete(cb);
}

function isConnected() {
  return !!(state.workspaceProvider && state.workspaceProvider.wsconnected);
}

function disconnect() {
  for (const path of Array.from(state.fileBindings.keys())) unbindEditor(path);
  if (state.workspaceProvider) {
    try { state.workspaceProvider.destroy(); } catch (_) {}
    state.workspaceProvider = null;
  }
  if (state.workspaceDoc) {
    try { state.workspaceDoc.destroy(); } catch (_) {}
    state.workspaceDoc = null;
  }
  state.workspaceId = null;
  state.token = null;
  state.role = null;
}

window.collab = {
  init, shareWorkspace, joinWithToken, joinDirect,
  bindEditor, listFiles, updateFileEntry, deleteFileEntry,
  onPresence, onFileTreeChange,
  isConnected, disconnect,
};
