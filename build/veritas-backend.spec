# build/veritas-backend.spec
# PyInstaller spec for bundling the AUA-Veritas Python backend.
#
# Usage:
#   cd /path/to/AUA-Veritas
#   pyinstaller build/veritas-backend.spec
#
# Output: dist/veritas-backend  (macOS single binary)

import sys
import os
from pathlib import Path

# Resolve project root from spec file location
spec_dir = Path(SPECPATH)
root = spec_dir.parent

block_cipher = None

# ── Collect all data files ────────────────────────────────────────────────────

datas = [
    # SQLite schema
    (str(root / 'db' / 'schema.sql'),        'db'),
    # Trigger model (spaCy classifier)
    (str(root / 'core' / 'trigger_model'),   'core/trigger_model'),
]

# Collect spaCy data files if present
try:
    import spacy
    spacy_path = Path(spacy.__file__).parent
    datas += [
        (str(spacy_path / 'lang'),  'spacy/lang'),
        (str(spacy_path / 'attrs.pyx'), 'spacy/'),
    ]
except Exception:
    pass

# ── Hidden imports ────────────────────────────────────────────────────────────
# Modules that PyInstaller misses via static analysis

hidden_imports = [
    # FastAPI / Starlette
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'fastapi',
    'fastapi.middleware',
    'starlette',
    'starlette.middleware',
    'starlette.middleware.cors',
    'pydantic',
    'pydantic.v1',
    # Keyring backends
    'keyring',
    'keyring.backends',
    'keyring.backends.macOS',
    'keyring.backends.SecretService',
    'keyring.backends.kwallet',
    # spaCy
    'spacy',
    'spacy.lang.en',
    'spacy.pipeline',
    'spacy.tokens',
    'spacy.vocab',
    'thinc',
    'blis',
    'murmurhash',
    'cymem',
    'preshed',
    'catalogue',
    'srsly',
    'wasabi',
    # SQLite (stdlib, but ensure it's included)
    'sqlite3',
    '_sqlite3',
    # Core modules
    'api.main',
    'core.router',
    'core.config',
    'core.state',
    'core.memory',
    'core.field_classifier',
    'core.utility_scorer',
    'core.confidence_updater',
    'core.arbiter',
    'core.validator',
    'core.guard',
    'core.policy',
    'core.hooks',
    'core.secrets',
    'core.session',
    'core.correction_loop',
    'core.trigger_detector',
    'core.memory_extractor',
    'core.scope_resolver',
    'core.store_utility',
    'core.include_utility',
    'core.restart_prompt',
    'core.plugins.openai_backend',
    'core.plugins.anthropic_backend',
    'core.plugins.google_backend',
    'core.plugins.xai_backend',
    'core.plugins.mistral_backend',
    'core.plugins.groq_backend',
    'core.plugins.deepseek_backend',
    # HTTP
    'httpx',
    'httpcore',
    'anyio',
    'anyio._backends._asyncio',
    'anyio._backends._trio',
    'h11',
]

# ── Analysis ──────────────────────────────────────────────────────────────────

a = Analysis(
    [str(root / 'build' / 'backend_launcher.py')],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[str(root / 'build' / 'hooks')],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude test/dev tools to keep bundle lean
        'pytest', 'IPython', 'jupyter', 'matplotlib',
        'setuptools', 'pip', 'wheel',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='veritas-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,           # UPX can cause issues on macOS
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,       # No terminal window
    disable_windowed_traceback=False,
    target_arch=None,    # Build for current arch; electron-builder handles universal
    codesign_identity=None,
    entitlements_file=None,
    icon=str(root / 'assets' / 'icon.icns') if (root / 'assets' / 'icon.icns').exists() else None,
)
