/* =============================================================================
 * Embedded collaboration host — runs INSIDE the Electron main process.
 *
 * When User 1 clicks "Share Workspace", their own app becomes the relay:
 * a tiny Y.js WebSocket server bound to their LAN address. Invitees on the
 * same network connect directly — no cloud server, no deployment, no cost.
 * The session dies when the host quits (same model as VS Code Live Share
 * peer sessions).
 *
 * Auth: a random per-session key baked into the share token. The WS upgrade
 * rejects any connection whose ?token= doesn't match.
 * ===========================================================================*/

const http = require('http');
const os = require('os');
const crypto = require('crypto');
const WebSocket = require('ws');
const Y = require('yjs');
const syncProtocol = require('y-protocols/sync');
const awarenessProtocol = require('y-protocols/awareness');
const encoding = require('lib0/encoding');
const decoding = require('lib0/decoding');

const MSG_SYNC = 0;
const MSG_AWARENESS = 1;

const state = {
  server: null,
  wss: null,
  port: 0,
  workspaceId: null,
  key: null,
  docs: new Map(), // docName → { ydoc, awareness, conns:Set }
};

function getLanIp() {
  const ifaces = os.networkInterfaces();
  for (const name of Object.keys(ifaces)) {
    for (const net of ifaces[name] || []) {
      if (net.family === 'IPv4' && !net.internal) return net.address;
    }
  }
  return '127.0.0.1';
}

function getDoc(docName) {
  if (state.docs.has(docName)) return state.docs.get(docName);
  const ydoc = new Y.Doc();
  const awareness = new awarenessProtocol.Awareness(ydoc);
  awareness.setLocalState(null);
  const entry = { ydoc, awareness, conns: new Set() };

  // Broadcast every document update to all peers except its origin.
  // Without this, an edit is applied to the server doc but other clients
  // only learn about it on their next full sync — i.e. never in practice.
  ydoc.on('update', (update, origin) => {
    const enc = encoding.createEncoder();
    encoding.writeVarUint(enc, MSG_SYNC);
    syncProtocol.writeUpdate(enc, update);
    const payload = encoding.toUint8Array(enc);
    for (const c of entry.conns) {
      if (c !== origin && c.readyState === WebSocket.OPEN) {
        try { c.send(payload); } catch (_) {}
      }
    }
  });

  awareness.on('update', ({ added, updated, removed }, origin) => {
    const changed = added.concat(updated, removed);
    if (!changed.length) return;
    const enc = encoding.createEncoder();
    encoding.writeVarUint(enc, MSG_AWARENESS);
    encoding.writeVarUint8Array(enc, awarenessProtocol.encodeAwarenessUpdate(awareness, changed));
    const payload = encoding.toUint8Array(enc);
    for (const c of entry.conns) {
      if (c !== origin && c.readyState === WebSocket.OPEN) { try { c.send(payload); } catch (_) {} }
    }
  });

  state.docs.set(docName, entry);
  return entry;
}

function handleConnection(conn, docName) {
  const entry = getDoc(docName);
  entry.conns.add(conn);
  conn._controlled = new Set();

  // Initial sync step 1 + current awareness.
  {
    const enc = encoding.createEncoder();
    encoding.writeVarUint(enc, MSG_SYNC);
    syncProtocol.writeSyncStep1(enc, entry.ydoc);
    try { conn.send(encoding.toUint8Array(enc)); } catch (_) {}
  }
  const states = entry.awareness.getStates();
  if (states.size > 0) {
    const enc = encoding.createEncoder();
    encoding.writeVarUint(enc, MSG_AWARENESS);
    encoding.writeVarUint8Array(enc,
      awarenessProtocol.encodeAwarenessUpdate(entry.awareness, Array.from(states.keys())));
    try { conn.send(encoding.toUint8Array(enc)); } catch (_) {}
  }

  conn.on('message', (data) => {
    try {
      const decoder = decoding.createDecoder(new Uint8Array(data));
      const enc = encoding.createEncoder();
      const type = decoding.readVarUint(decoder);
      if (type === MSG_SYNC) {
        encoding.writeVarUint(enc, MSG_SYNC);
        // Applies incoming updates to the doc (origin = conn, so the
        // ydoc.on('update') broadcast skips the sender) and writes any
        // required sync reply for the sender only.
        syncProtocol.readSyncMessage(decoder, enc, entry.ydoc, conn);
        if (encoding.length(enc) > 1) {
          try { conn.send(encoding.toUint8Array(enc)); } catch (_) {}
        }
      } else if (type === MSG_AWARENESS) {
        awarenessProtocol.applyAwarenessUpdate(entry.awareness, decoding.readVarUint8Array(decoder), conn);
      }
    } catch (err) {
      console.error('[collab-host] message error', err.message);
    }
  });

  conn.on('close', () => {
    entry.conns.delete(conn);
    if (conn._controlled.size) {
      awarenessProtocol.removeAwarenessStates(entry.awareness, Array.from(conn._controlled), null);
    }
  });
}

/** Start (or return the already-running) host session. */
function startHost() {
  return new Promise((resolve, reject) => {
    if (state.server) {
      return resolve(hostInfo());
    }
    state.workspaceId = crypto.randomUUID();
    state.key = crypto.randomBytes(16).toString('hex');

    const server = http.createServer((req, res) => {
      // Minimal HTTP: /verify for the join modal's pre-flight check.
      if (req.method === 'POST' && req.url === '/verify') {
        let body = '';
        req.on('data', (c) => { body += c; if (body.length > 4096) req.destroy(); });
        req.on('end', () => {
          let ok = false;
          try {
            const j = JSON.parse(body);
            ok = j.workspace_id === state.workspaceId && j.key === state.key;
          } catch (_) {}
          res.setHeader('Content-Type', 'application/json');
          res.setHeader('Access-Control-Allow-Origin', '*');
          res.end(JSON.stringify({ valid: ok }));
        });
        return;
      }
      if (req.method === 'OPTIONS') {
        res.setHeader('Access-Control-Allow-Origin', '*');
        res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
        res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
        res.writeHead(204); res.end();
        return;
      }
      res.writeHead(404); res.end();
    });

    const wss = new WebSocket.Server({ noServer: true });
    server.on('upgrade', (request, socket, head) => {
      try {
        const url = new URL(request.url, `http://${request.headers.host}`);
        const m = url.pathname.match(/^\/ws\/([\w\-]+)$/);
        const token = url.searchParams.get('token') || '';
        if (!m || m[1] !== state.workspaceId || token !== state.key) {
          socket.write('HTTP/1.1 401 Unauthorized\r\n\r\n');
          socket.destroy();
          return;
        }
        const subDoc = url.searchParams.get('doc') || state.workspaceId;
        const docName = subDoc.startsWith(state.workspaceId) ? subDoc : `${state.workspaceId}/${subDoc}`;
        wss.handleUpgrade(request, socket, head, (ws) => handleConnection(ws, docName));
      } catch (_) {
        socket.destroy();
      }
    });

    server.on('error', (err) => reject(err));
    server.listen(0, '0.0.0.0', () => {
      state.server = server;
      state.wss = wss;
      state.port = server.address().port;
      console.log(`[collab-host] session ${state.workspaceId.slice(0, 8)}… on :${state.port}`);
      resolve(hostInfo());
    });
  });
}

function hostInfo() {
  return {
    running: !!state.server,
    workspaceId: state.workspaceId,
    key: state.key,
    port: state.port,
    url: `ws://${getLanIp()}:${state.port}`,
    localUrl: `ws://127.0.0.1:${state.port}`,
  };
}

function stopHost() {
  if (state.wss) { try { state.wss.close(); } catch (_) {} }
  if (state.server) { try { state.server.close(); } catch (_) {} }
  for (const entry of state.docs.values()) { try { entry.ydoc.destroy(); } catch (_) {} }
  state.docs.clear();
  state.server = null; state.wss = null; state.port = 0;
  state.workspaceId = null; state.key = null;
  return { running: false };
}

module.exports = { startHost, stopHost, hostInfo };
