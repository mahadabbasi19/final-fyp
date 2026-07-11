<div align="center">

<img src="images/logo_codenova.png" alt="CodeNova AI" width="120" />

# CodeNova AI

### The AI-native desktop IDE for Java — refactor, collaborate, and ship faster.

A VS Code–style desktop editor that pairs a **behavior-preserving refactoring engine** with **real-time collaboration**, a **live dependency graph**, and a **built-in AI assistant** — all in one fast, offline-capable app.

[![Website](https://img.shields.io/badge/🌐_Visit-codenovaa.com-7c3aed?style=for-the-badge)](https://codenovaa.com/)
[![Download](https://img.shields.io/badge/Download-Windows%20%7C%20macOS-1f883d?style=for-the-badge&logo=github)](https://github.com/mahadabbasi19/final-fyp/releases/latest)
[![Build](https://img.shields.io/badge/CI-GitHub%20Actions-2088FF?style=for-the-badge&logo=githubactions&logoColor=white)](../../actions)

**🌐 [codenovaa.com](https://codenovaa.com/)** &nbsp;·&nbsp; Windows & macOS &nbsp;·&nbsp; 64-bit &nbsp;·&nbsp; Free

</div>

---

## ✨ Overview

**CodeNova AI** is a standalone desktop IDE built for Java developers who want the power of a modern editor without the setup friction. It combines four pillars into a single, cohesive product:

| Pillar | What it does |
| --- | --- |
| 🧠 **Refactoring Engine** | AST-driven, behavior-preserving transformations with an automatic **rollback safety net** — if a change can't be proven safe, it's refused, never applied. |
| 🩺 **Real-Time Diagnostics** | Syntax + runtime-risk detection, cyclomatic complexity, Halstead metrics, and a Maintainability Index — updated as you type. |
| 👥 **Live Collaboration** | CRDT-based multi-user editing (Y.js). Share a workspace on your LAN with **zero setup**, or worldwide through a lightweight relay. |
| 🤖 **CodeNova Assistant** | A white-labeled, built-in AI that explains, generates, and delegates refactors to the deterministic engine. |

> **Design philosophy — fail safe, never corrupt.** Where correctness can't be guaranteed, the engine declines or rolls back rather than risk altering your code's behavior.

---

## 🚀 Download & Install

**➡️ Get it from the official site: [codenovaa.com](https://codenovaa.com/)** — the download button auto-detects your OS. Or grab the installer directly from the [**Releases**](https://github.com/mahadabbasi19/final-fyp/releases/latest) page:

| Platform | File | First-run note |
| --- | --- | --- |
| **Windows 10/11** (64-bit) | `CodeNova-IDE-Setup-2.0.0.exe` | If Windows shows *"Windows protected your PC"* → **More info → Run anyway** (the app is unsigned, nothing is wrong). |
| **macOS 12+** (Apple Silicon) | `CodeNova-IDE-2.0.0-macOS.dmg` | Right-click the app → **Open → Open** (needed once for apps outside the App Store). |

**No prerequisites** — Python and Node.js runtimes are bundled. A **Java JDK** is optional and only needed to compile/run Java code inside the IDE (the app detects it automatically and prompts you if it's missing).

---

## 🧩 Features

### 🧠 Behavior-Preserving Refactoring
- **Deterministic transforms** (safety score = 1.0): dead-code elimination, unused-import removal, condition simplification (De Morgan's laws), guard-clause introduction.
- **Heuristic transforms** (advisory): extract method, decompose behavior, class-split previews, duplicate consolidation.
- **Five-gate safety net** on every change — bracket balance, AST re-parse, method-signature preservation, static-error delta, and (with a JDK) a **javac compile + javap API-surface diff**. Any failure ⇒ automatic rollback.

### 🩺 Code Intelligence
- Real-time **syntax errors** (exact line/column via the `javalang` parser; full `javac` diagnostics when a JDK is present).
- **Runtime-risk warnings** — provable array-bounds violations, null-dereference heuristics, division-by-zero, resource leaks.
- **Metrics dashboard** — cyclomatic complexity, Halstead volume/effort, Maintainability Index, coupling & cohesion.
- **Live dependency graph** — a directional, canvas-rendered map of class relationships (extends / implements / uses).

### 👥 Real-Time Collaboration
- **Conflict-free** editing powered by [Y.js](https://github.com/yjs/yjs) CRDTs — concurrent edits merge character-by-character, no merge dialogs.
- **Same-network mode:** your app becomes the host — share a token, teammates join instantly. No server, no accounts.
- **Worldwide mode:** connect through a small relay (deployable to any free tier in minutes).
- Presence indicators and remote cursors.

### 🔗 Git, Built In
- Full Source Control panel: stage, commit, branch, stash, diff, log.
- **Push to GitHub** with your own Personal Access Token — commits are attributed to *your* account.
- Non-interactive by design: network ops fail fast with actionable messages instead of hanging.

### 💻 A Real Editor
- **Monaco** editor core (the engine behind VS Code), integrated terminal (`xterm.js` + `node-pty`), multi-tab layout, file explorer, workspace search, and a configurable settings page.

---

## 🏗️ Architecture

```
┌──────────────────────── Electron Desktop App ────────────────────────┐
│  Renderer (Monaco · xterm.js · Canvas graph · Chat UI)               │
│        │  IPC (context-isolated, token-authenticated)                │
│  Main process (Node.js)                                              │
│    ├── spawns  ──►  Python backend  (bundled binary, no Python req.)  │
│    └── hosts   ──►  Embedded collab relay (Y.js WebSocket, on demand) │
└───────────────────────────────┬──────────────────────────────────────┘
                                │  HTTP · 127.0.0.1 · X-CodeNova-Token
                                ▼
┌──────────────── FastAPI Backend (Python) ────────────────┐
│  Refactoring Engine  ·  AST Parser (javalang)            │
│  Error Checker       ·  Metrics (Halstead · MI · CC)     │
│  Git Manager (GitPython)  ·  AI controller (white-label) │
└───────────────────────────────────────────────────────────┘
```

**Repository layout**

| Path | Description |
| --- | --- |
| [`desktop-app/`](desktop-app) | Electron shell — main process, preload bridge, renderer UI, embedded collab host. |
| [`java_refactoring_engine/`](java_refactoring_engine) | FastAPI backend — refactoring engine, AST parser, error checker, metrics, git manager (**39 REST endpoints**). |
| [`collab-server/`](collab-server) | Standalone worldwide collaboration relay (Y.js + JWT + LevelDB). |
| [`website/`](website) | Marketing site with OS-aware download buttons. |
| [`.github/workflows/`](.github/workflows) | CI that builds the Windows installer on GitHub's runners. |

---

## 🛠️ Tech Stack

**Frontend** — Electron · Monaco Editor · xterm.js · HTML5 Canvas · vanilla JS
**Backend** — Python · FastAPI · Uvicorn · PyInstaller (standalone binary)
**Parsing & Analysis** — javalang (Java AST) · javac/javap integration · custom static analyzers
**Collaboration** — Y.js (CRDT) · WebSockets · JWT · LevelDB
**Version Control** — Git · GitPython · GitHub Actions
**AI** — GPT-4o (white-labeled behind the CodeNova assistant layer)

---

## 👩‍💻 Build from Source

**Prerequisites:** Node.js 20+, Python 3.11+, Git. (JDK optional, for Java compile/run.)

```bash
git clone https://github.com/mahadabbasi19/final-fyp.git
cd final-fyp

# 1) Backend deps
cd java_refactoring_engine
python -m venv .venv
.venv/bin/pip install -r requirements.txt          # Windows: .venv\Scripts\pip
#   (optional) add your AI key:  echo "OPENAI_API_KEY=sk-..." > .env

# 2) Desktop app
cd ../desktop-app
npm install
npm run build:collab        # bundle the collaboration client
npm start                   # launch the IDE in dev mode
```

**Package installers**

```bash
# Backend → standalone binary (run on each target OS; PyInstaller doesn't cross-compile)
cd java_refactoring_engine
.venv/bin/python -m PyInstaller codenova-backend.spec --noconfirm

# Installer
cd ../desktop-app
npm run dist        # Windows: → dist/CodeNova IDE Setup 2.0.0.exe
npm run dist:mac    # macOS:   → dist/CodeNova IDE-2.0.0-arm64.dmg
```

Prefer zero setup? The [**Build Windows Installer**](../../actions) workflow compiles the `.exe` on GitHub's runners — just click *Run workflow*.

---

## 🔐 Security & Privacy

- **Local-first.** Files, projects, git history, and settings never leave your machine.
- **Authenticated backend.** The local API is gated by a per-launch random token; a strict CSP and context isolation lock down the renderer.
- **No telemetry.** Offline for everything except the optional AI assistant.

---

## 📈 Project Status

CodeNova AI (v2.0.0) is a complete, distributable product. Known limitations and the future-work roadmap (type-aware cross-file rename, semantic clone detection, code signing) are documented in [`PUBLISHING.md`](PUBLISHING.md) and the project report.

---

<div align="center">

**Built with ❤️ as a Final Year Project.**

*CodeNova AI — code at the speed of thought.*

</div>
