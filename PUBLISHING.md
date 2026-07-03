# CodeNova IDE — Publishing Guide

Complete checklist for shipping the desktop app to the public.
(.exe for Windows, .dmg for macOS.)

---

## PART 1 — Before publishing (one-time setup, ~30 minutes)

### 1.1 Rotate the OpenAI API key  ⚠️ DO THIS FIRST
The old key is exposed in public git history (commit 4336d8e).
1. Go to https://platform.openai.com/api-keys
2. Revoke the old key (`sk-proj-WZkUQK…`)
3. Create a new key
4. Paste it into `java_refactoring_engine/.env` (this file is gitignored):
   `OPENAI_API_KEY=sk-proj-NEW-KEY`
5. Set a hard monthly spend limit at https://platform.openai.com/settings/organization/limits
   (every downloader shares this key — cap your risk, e.g. $10/month)

### 1.2 Add the key as a GitHub Actions secret
So cloud builds bake the key into the backend binary:
1. Repo → Settings → Secrets and variables → Actions → New repository secret
2. Name: `OPENAI_API_KEY`  ·  Value: the new key

### 1.3 Create the GitHub OAuth App (enables "Sign in with GitHub")
1. https://github.com/settings/applications/new
2. Application name: `CodeNova IDE`
   Homepage URL: `https://github.com/mahadabbasi19/final-fyp`
   Callback URL: `http://127.0.0.1` (unused by device flow, any value works)
3. ✅ Tick **"Enable Device Flow"**  ← critical
4. Register → copy the **Client ID** (e.g. `Ov23li…`)
5. In `desktop-app/main.js`, replace `REPLACE_WITH_OAUTH_APP_CLIENT_ID`
   with your Client ID. Commit + push. (Client IDs are public — safe.)

### 1.4 Deploy the collaboration relay (optional — only for live collab over internet)
Local demos work with `node collab-server/server.js` on one machine.
For worldwide use, deploy the `collab-server/` folder to Railway/Fly.io/Render:
1. Create the service from the repo subfolder `collab-server`
2. Set env vars: `JWT_SECRET` (generate: `openssl rand -hex 32`), `PORT` (platform default)
3. Note the public URL, e.g. `wss://codenova-relay.up.railway.app`
4. In `desktop-app/renderer.js`, change `COLLAB_RELAY_DEFAULT` fallback from
   `ws://127.0.0.1:1234` to your `wss://…` URL (users can still override in the 📡 menu)

### 1.5 Version + final smoke test
1. Bump `"version"` in `desktop-app/package.json` (e.g. `2.1.0`)
2. Run the app once (`npm start`), verify: file open/save, terminal,
   error squiggles, refactor with diff preview, chat, push, collab share/join.

---

## PART 2 — Build the Windows .exe

### Option A (recommended): GitHub Actions — no Windows machine needed
Already configured in `.github/workflows/build-windows.yml`.
1. Go to https://github.com/mahadabbasi19/final-fyp/actions
2. Select **Build Windows Installer** → **Run workflow** → Run
3. Wait ~10–15 min
4. Open the finished run → **Artifacts** → download `CodeNova-IDE-Windows`
   Contains: `CodeNova IDE Setup <version>.exe` (installer) and
   `CodeNova-IDE-Portable-<version>.exe`

To publish as a release instead (gives you a permanent download URL):
```bash
git tag v2.1.0
git push --tags
```
The workflow attaches the .exe files to a GitHub Release automatically.
Your website's Download button links to:
`https://github.com/mahadabbasi19/final-fyp/releases/latest`

### Option B: On a Windows machine
Prerequisites: Node.js 20+, Python 3.11+, Git.
```powershell
git clone https://github.com/mahadabbasi19/final-fyp.git
cd final-fyp\java_refactoring_engine

# backend → standalone .exe (no Python needed by end users)
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt pyinstaller
# create .env with your key first:  echo OPENAI_API_KEY=sk-... > .env
.venv\Scripts\python -m PyInstaller codenova-backend.spec --noconfirm
# → dist\codenova-backend.exe

cd ..\desktop-app
npm install
npm run dist
# → dist\CodeNova IDE Setup <version>.exe  +  portable .exe
```

### Windows caveats
- **SmartScreen**: unsigned .exe shows "Windows protected your PC".
  Users click "More info → Run anyway". Eliminating this requires a paid
  code-signing certificate (~$100–400/yr) — skip for FYP, mention it on
  your download page.
- Antivirus may sandbox the PyInstaller backend on first run (~10 s delay).

---

## PART 3 — Build the macOS .dmg

Config is already in `package.json` (`mac` + `dmg` sections, `icon.icns` generated).

### On this Mac (Apple Silicon):
```bash
cd ~/Desktop/FYP/java_refactoring_engine
# backend binary — already built at dist/codenova-backend (arm64).
# Rebuild after changing .env or backend code:
.venv/bin/python -m PyInstaller codenova-backend.spec --noconfirm

cd ../desktop-app
unset ELECTRON_RUN_AS_NODE
npm run dist:mac -- --arm64        # → dist/CodeNova IDE-<version>-arm64.dmg
```

### macOS caveats — read these
1. **Architecture**: the backend binary built on this Mac is arm64-only.
   An Intel (x64) .dmg would ship a backend that cannot run on Intel Macs.
   → Ship the arm64 .dmg only (covers all Macs from 2020 onward), or build
   the backend on an Intel Mac / GitHub's `macos-13` runner for an x64 dmg.
2. **Gatekeeper**: the app is unsigned (`"identity": null`), so first launch
   requires right-click → Open → Open (or System Settings → Privacy &
   Security → Open Anyway). Removing this needs an Apple Developer account
   ($99/yr) + notarization — not worth it for an FYP.
3. Distribute the .dmg the same way: attach it to the GitHub Release.

### Cloud alternative for macOS
Add a `macos-latest` job to the workflow (mirror of the Windows job with
`npm run dist:mac -- --arm64` and `pyinstaller` on the runner) — ask me and
I'll add it.

---

## PART 4 — Publish

1. **Tag a release**: `git tag v2.1.0 && git push --tags`
   → Actions builds and attaches the Windows .exe automatically.
   → Upload the .dmg to the same release manually
     (repo → Releases → edit → attach file), or add the mac CI job.
2. **Website**: point your hosting's Download buttons at the release assets:
   - Windows: `…/releases/download/v2.1.0/CodeNova.IDE.Setup.2.1.0.exe`
   - macOS:   `…/releases/download/v2.1.0/CodeNova.IDE-2.1.0-arm64.dmg`
3. **On the download page, state clearly**:
   - Windows 10/11 64-bit · macOS 12+ (Apple Silicon)
   - No prerequisites (Python/Node NOT required — bundled)
   - Java JDK optional — only needed to compile/run Java inside the IDE
   - The SmartScreen / Gatekeeper "unsigned app" instructions

---

## Quick answer sheet

| Question | Answer |
|---|---|
| Do end users need Python? | No — backend is a bundled binary |
| Do end users need Node? | No — Electron bundles its runtime |
| Do end users need Java? | Only for compiling/running Java code |
| Do end users need any account? | GitHub only if they want to push; OpenAI key is yours (shared) |
| Windows + macOS from one machine? | .exe via GitHub Actions from anywhere; .dmg needs a Mac (you have one) |
| Total cost to publish? | $0 (unsigned builds + GitHub Releases + free relay hosting) |
