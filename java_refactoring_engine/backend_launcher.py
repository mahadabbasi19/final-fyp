"""
PyInstaller entry point for the CodeNova backend.

Produces a standalone binary (no Python required on the end-user machine) —
this is what lets the installed IDE work like VS Code: download, run, done.

Build (run on the TARGET platform — PyInstaller does not cross-compile):
    Windows:  .venv\\Scripts\\python -m PyInstaller codenova-backend.spec
    macOS  :  .venv/bin/python -m PyInstaller codenova-backend.spec
Output: dist/codenova-backend(.exe)
"""

import multiprocessing
import os
import sys

# PyInstaller-frozen processes re-exec themselves; without this guard
# uvicorn's reload/workers machinery can fork-bomb.
multiprocessing.freeze_support()


def main() -> None:
    # When frozen, resources live next to the executable.
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
        os.chdir(base)
        sys.path.insert(0, base)

    import uvicorn
    from main import app

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=int(os.environ.get("CODENOVA_BACKEND_PORT", "8000")),
        log_level="info",
    )


if __name__ == "__main__":
    main()
