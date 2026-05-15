"""
build/backend_launcher.py — PyInstaller entry point for AUA-Veritas backend.

This script is the entry point when the Python backend is packaged by PyInstaller.
It starts uvicorn with the FastAPI app on port 47821.

PyInstaller bundles this + all dependencies into a single binary:
  dist/veritas-backend  (macOS/Linux)
  dist/veritas-backend.exe  (Windows)

The Electron main process starts this binary instead of python/uvicorn directly.
"""
import sys
import os
import multiprocessing

# Required for PyInstaller on macOS (multiprocessing + frozen apps)
multiprocessing.freeze_support()

# Add the bundled app directory to sys.path so imports work
if getattr(sys, 'frozen', False):
    # Running as PyInstaller bundle
    bundle_dir = sys._MEIPASS
    sys.path.insert(0, bundle_dir)
    # Set working directory to bundle dir so relative paths resolve
    os.chdir(bundle_dir)

import uvicorn

if __name__ == '__main__':
    # Port can be overridden via environment variable
    port = int(os.environ.get('VERITAS_API_PORT', '47821'))
    host = os.environ.get('VERITAS_API_HOST', '127.0.0.1')

    uvicorn.run(
        'api.main:app',
        host=host,
        port=port,
        log_level='warning',
        access_log=False,
    )
