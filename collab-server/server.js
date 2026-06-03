/* =============================================================================
 * CodeNova IDE — Real-time collaboration relay.
 *
 * Responsibilities:
 *   1. Mint short-lived JWT tokens that encode { workspace_id, role }.
 *   2. Accept WebSocket connections under /ws/:workspaceId, gated by a JWT
 *      passed as the `token` query string.
 *   3. Relay Y.js sync + awareness messages between peers in the same
 *      workspace, persisting docs to LevelDB so late joiners catch up.
 *
 * Endpoints (HTTP):
 *   POST /token   { workspace_id?, role?, ttl_hours? }  → { token, workspace_id }
 *   POST /verify  { token }                               → { valid, payload }
 *   GET  /health                                          → { ok: true }
 *
 * WebSocket:
 *   wss://host/ws/:workspaceId?token=<jwt>
 *
 * Persistence:
 *   LevelDB at process.env.PERSIST_DIR (default ./y-leveldb).
 *   One key per workspace doc; one per file doc (`<workspaceId>/<file>`).
 * ===========================================================================*/

const fs = require('fs');
const path = require('path');
const http = require('http');
const express = require('express');
const jwt = require('jsonwebtoken');
const { WebSocketServer } = require('ws');
const { v4: uuidv4 } = require('uuid');
const Y = require('yjs');
const syncProtocol = require('y-protocols/sync');
const awarenessProtocol = require('y-protocols/awareness');
const encoding = require('lib0/encoding');
const decoding = require('lib0/decoding');
const { LeveldbPersistence } = require('y-leveldb');

// ── Minimal .env loader so we don't pull dotenv in ─────────────────────────
const envPath = path.join(__dirname, '.env');
if (fs.existsSync(envPath)) {
  for (const line of fs.readFileSync(envPath, 'utf8').split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#') || !trimmed.includes('=')) continue;
    const idx = trimmed.indexOf('=');
    const k = trimmed.slice(0, idx).trim();
    const v = trimmed.slice(idx + 1).trim().replace(/^["']|["']$/g, '');
    if (k && !(k in process.env)) process.env[k] = v;
  }
}

const JWT_SECRET = process.env.JWT_SECRET || '';
if (!JWT_SECRET || JWT_SECRET === 'replace-me-with-a-long-random-string') {
  console.error('FATAL: JWT_SECRET is not set. Generate one with `openssl rand -hex 32` and put it in .env.');
  process.exit(1);
}
const PORT = parseInt(process.env.PORT || '1234', 10);
const PERSIST_DIR = process.env.PERSIST_DIR || './y-leveldb';
const ALLOWED_ORIGINS = (process.env.ALLOWED_ORIGINS || '*')
  .split(',')
  .map((s) => s.trim());

// ── Persistence ────────────────────────────────────────────────────────────
const persistence = new LeveldbPersistence(PERSIST_DIR);

// ── HTTP layer (JWT mint / verify / health) ────────────────────────────────
const app = express();
app.use(express.json({ limit: '64kb' }));

app.use((req, res, next) => {
  const origin = req.headers.origin;
  if (ALLOWED_ORIGINS.includes('*') || (origin && ALLOWED_ORIGINS.includes(origin))) {
    res.setHeader('Access-Control-Allow-Origin', origin || '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  }
  if (req.method === 'OPTIONS') return res.sendStatus(204);
  next();
});

app.get('/health', (_req, res) => res.json({ ok: true, version: '1.0.0' }));

/**
 * POST /token
 * Body: { workspace_id?, role?, ttl_hours? }
 * Issues a JWT scoped to a workspace. If `workspace_id` is omitted, a new
 * one is minted. If `role` is omitted, defaults to 'editor'.
 */
app.post('/token', (req, res) => {
  const workspaceId = (req.body.workspace_id || uuidv4()).slice(0, 64);
  const role = ['viewer', 'editor', 'owner'].includes(req.body.role) ? req.body.role : 'editor';
  const ttlHours = Math.max(1, Math.min(24 * 30, parseInt(req.body.ttl_hours || '168', 10))); // default 7d, cap 30d
  const token = jwt.sign(
    { workspace_id: workspaceId, role },
    JWT_SECRET,
    { expiresIn: `${ttlHours}h` },
  );
  res.json({ token, workspace_id: workspaceId, role, expires_in_hours: ttlHours });
});

/**
 * POST /verify
 * Body: { token }
 * Returns whether a token is currently valid (used by the IDE's Join modal
 * to give immediate feedback before opening a WS).
 */
app.post('/verify', (req, res) => {
  try {
    const payload = jwt.verify(req.body.token || '', JWT_SECRET);
    res.json({ valid: true, payload });
  } catch (err) {
    res.json({ valid: false, error: err.message });
  }
});

// ── WebSocket layer (Y.js sync + awareness) ────────────────────────────────
const server = http.createServer(app);
const wss = new WebSocketServer({ noServer: true });

const MSG_SYNC = 0;
const MSG_AWARENESS = 1;

// docName → { ydoc, awareness, conns: Map<ws, Set<clientID>> }
const docs = new Map();

async function getDoc(docName) {
  if (docs.has(docName)) return docs.get(docName);

  const ydoc = new Y.Doc();
  // Load persisted state.
  const persisted = await persistence.getYDoc(docName);
  Y.applyUpdate(ydoc, Y.encodeStateAsUpdate(persisted));
  // Flush updates to LevelDB on every change.
  ydoc.on('update', (update) => {
    persistence.storeUpdate(docName, update).catch((err) =>
      console.error('[persist] storeUpdate failed', docName, err.message),
    );
  });

  const awareness = new awarenessProtocol.Awareness(ydoc);
  awareness.setLocalState(null);

  const entry = { ydoc, awareness, conns: new Map() };

  // Broadcast awareness changes to every peer in this doc.
  awareness.on('update', ({ added, updated, removed }, origin) => {
    const changed = added.concat(updated, removed);
    if (changed.length === 0) return;
    const encoder = encoding.createEncoder();
    encoding.writeVarUint(encoder, MSG_AWARENESS);
    encoding.writeVarUint8Array(
      encoder,
      awarenessProtocol.encodeAwarenessUpdate(awareness, changed),
    );
    const payload = encoding.toUint8Array(encoder);
    for (const conn of entry.conns.keys()) {
      if (conn !== origin && conn.readyState === conn.OPEN) {
        try { conn.send(payload); } catch (_) {}
      }
    }
  });

  docs.set(docName, entry);
  return entry;
}

function send(conn, encoder) {
  if (conn.readyState !== conn.OPEN) return;
  try {
    conn.send(encoding.toUint8Array(encoder));
  } catch (_) {
    conn.close();
  }
}

async function onConnection(conn, docName, payload) {
  const entry = await getDoc(docName);
  // Register connection.
  entry.conns.set(conn, new Set());
  conn._role = payload.role;
  conn._workspaceId = payload.workspace_id;

  // 1. Send initial Y.js sync step 1.
  {
    const encoder = encoding.createEncoder();
    encoding.writeVarUint(encoder, MSG_SYNC);
    syncProtocol.writeSyncStep1(encoder, entry.ydoc);
    send(conn, encoder);
  }
  // 2. Send current awareness state.
  const awarenessStates = entry.awareness.getStates();
  if (awarenessStates.size > 0) {
    const encoder = encoding.createEncoder();
    encoding.writeVarUint(encoder, MSG_AWARENESS);
    encoding.writeVarUint8Array(
      encoder,
      awarenessProtocol.encodeAwarenessUpdate(
        entry.awareness,
        Array.from(awarenessStates.keys()),
      ),
    );
    send(conn, encoder);
  }

  conn.on('message', (data) => {
    try {
      const decoder = decoding.createDecoder(new Uint8Array(data));
      const encoder = encoding.createEncoder();
      const messageType = decoding.readVarUint(decoder);
      switch (messageType) {
        case MSG_SYNC: {
          if (conn._role === 'viewer') break; // read-only
          encoding.writeVarUint(encoder, MSG_SYNC);
          syncProtocol.readSyncMessage(decoder, encoder, entry.ydoc, conn);
          // Broadcast resulting update to other peers.
          if (encoding.length(encoder) > 1) {
            const payload = encoding.toUint8Array(encoder);
            // First, reply to the sender so it acks step 2.
            send(conn, encoder);
            // Then broadcast the new state to siblings.
            for (const other of entry.conns.keys()) {
              if (other !== conn && other.readyState === other.OPEN) {
                try { other.send(payload); } catch (_) {}
              }
            }
          }
          break;
        }
        case MSG_AWARENESS: {
          awarenessProtocol.applyAwarenessUpdate(
            entry.awareness,
            decoding.readVarUint8Array(decoder),
            conn,
          );
          break;
        }
        default:
          break;
      }
    } catch (err) {
      console.error('[ws] message error', err.message);
    }
  });

  conn.on('close', () => {
    const controlled = entry.conns.get(conn);
    entry.conns.delete(conn);
    if (controlled && controlled.size > 0) {
      awarenessProtocol.removeAwarenessStates(
        entry.awareness,
        Array.from(controlled),
        null,
      );
    }
    if (entry.conns.size === 0) {
      // Optional: free the doc from memory after a grace period.
      setTimeout(() => {
        if (docs.get(docName) === entry && entry.conns.size === 0) {
          docs.delete(docName);
          entry.ydoc.destroy();
        }
      }, 60_000);
    }
  });
}

server.on('upgrade', (request, socket, head) => {
  const url = new URL(request.url, `http://${request.headers.host}`);
  const match = url.pathname.match(/^\/ws\/([\w\-]+)$/);
  if (!match) {
    socket.write('HTTP/1.1 404 Not Found\r\n\r\n');
    socket.destroy();
    return;
  }
  const wsWorkspaceId = match[1];
  const token = url.searchParams.get('token') || '';
  let payload;
  try {
    payload = jwt.verify(token, JWT_SECRET);
  } catch (err) {
    socket.write('HTTP/1.1 401 Unauthorized\r\n\r\n');
    socket.destroy();
    return;
  }
  if (payload.workspace_id !== wsWorkspaceId) {
    socket.write('HTTP/1.1 403 Forbidden\r\n\r\n');
    socket.destroy();
    return;
  }
  wss.handleUpgrade(request, socket, head, (ws) => {
    // Doc name = `<workspaceId>` for the workspace meta doc, plus
    // `<workspaceId>/<filename>` for per-file docs. The client decides
    // which by sub-pathing the URL.
    const subDoc = url.searchParams.get('doc') || wsWorkspaceId;
    const docName = subDoc.startsWith(wsWorkspaceId) ? subDoc : `${wsWorkspaceId}/${subDoc}`;
    onConnection(ws, docName, payload);
  });
});

server.listen(PORT, () => {
  console.log(`[collab] HTTP+WS listening on :${PORT}`);
  console.log(`[collab] persisting to ${path.resolve(PERSIST_DIR)}`);
});

// Graceful shutdown — flush LevelDB.
process.on('SIGTERM', async () => {
  console.log('[collab] SIGTERM — flushing persistence');
  await persistence.destroy().catch(() => {});
  process.exit(0);
});
