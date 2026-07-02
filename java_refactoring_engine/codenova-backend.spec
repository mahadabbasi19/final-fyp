# PyInstaller spec for the CodeNova backend.
# Build on the target platform:
#   .venv/bin/python -m PyInstaller codenova-backend.spec        (macOS/Linux)
#   .venv\Scripts\python -m PyInstaller codenova-backend.spec    (Windows)

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = (
    collect_submodules('uvicorn')
    + collect_submodules('javalang')
    + collect_submodules('git')
    + [
        'main',
        'ast_parser',
        'error_checker',
        'refactoring_engine',
        'metrics',
        'git_manager',
        'history',
    ]
)

a = Analysis(
    ['backend_launcher.py'],
    pathex=['.'],
    binaries=[],
    # Ship .env next to the binary so the OpenAI key loads exactly as in dev.
    datas=[('.env', '.')],
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name='codenova-backend',
    debug=False,
    strip=False,
    upx=False,
    console=True,          # keep console output for the Electron log pipe
    disable_windowed_traceback=False,
)
