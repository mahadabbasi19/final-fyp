# CodeNova Collaboration Relay

Real-time CRDT-based collaboration relay for the CodeNova IDE. Powers the
"Share Workspace" / "Join Workspace" flow.

## Architecture
- **Y.js** for CRDT-based document merging (conflict-free by construction).
- **y-websocket** relay protocol over plain WSS — every peer connects to the
  same docName and receives sync + awareness updates.
- **JWT** for stateless authorization. The token encodes
  `{ workspace_id, role, exp }`. The WS upgrade verifies the JWT and rejects
  if `workspace_id` in the URL doesn't match the token.
- **LevelDB** (`y-leveldb`) for persistence — late joiners get the full doc.

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/token`  | Mint a JWT. Body: `{ workspace_id?, role?, ttl_hours? }`. Server invents `workspace_id` if omitted. |
| `POST` | `/verify` | Body: `{ token }` → `{ valid, payload }`. Used by the Join modal. |
| `GET`  | `/health` | Liveness probe. |
| `WS`   | `/ws/:workspaceId?token=<jwt>&doc=<docName>` | Open a Y.js sync channel. `doc` defaults to the workspace meta doc. |

## Deploy

```bash
cd collab-server
cp .env.example .env
# Edit .env — set JWT_SECRET to: openssl rand -hex 32
npm install
npm start
```

For production behind TLS, terminate WSS at your reverse proxy
(nginx / Caddy / Cloudflare) and point the IDE's `collab.relayUrl` setting
at `wss://your.domain.com`.

### Hosting options
- **Fly.io / Railway / Render free tier** — fits inside their always-free
  envelopes. LevelDB persists to a volume.
- **Self-hosted VPS** — single Node process, no external services required.
- **AWS / GCP** — overkill for this load; one t4g.nano is plenty.

## Storage notes
- One LevelDB key per docName.
- Workspace doc = `<workspaceId>`.
- Per-file docs = `<workspaceId>/<urlencoded path>`.
- Tombstoning unused workspaces should be done with a cron that deletes
  workspaces older than N days with zero connected peers.
