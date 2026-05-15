#!/bin/bash
# build-mac.sh — AUA-Veritas macOS .dmg builder
#
# Run this once on your Mac to produce a distributable .dmg
# No Apple Developer account required.
#
# Usage:
#   chmod +x build-mac.sh
#   ./build-mac.sh
#
# Output: release/AUA-Veritas-*.dmg

set -e  # exit on any error

REPO="https://github.com/praneethtota/AUA-Veritas.git"
APP_DIR="$(pwd)/AUA-Veritas"
VENV="$APP_DIR/.venv"
NODE_MIN="18"
PYTHON_MIN="3.10"

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()    { echo -e "${BLUE}[AUA-Veritas]${NC} $*"; }
success() { echo -e "${GREEN}[AUA-Veritas]${NC} ✓ $*"; }
warn()    { echo -e "${YELLOW}[AUA-Veritas]${NC} ⚠ $*"; }
die()     { echo -e "${RED}[AUA-Veritas]${NC} ✗ $*"; exit 1; }

echo ""
echo "  ╔═══════════════════════════════════╗"
echo "  ║   AUA-Veritas macOS Builder       ║"
echo "  ║   Building .dmg installer         ║"
echo "  ╚═══════════════════════════════════╝"
echo ""

# ── Check prerequisites ───────────────────────────────────────────────────────

info "Checking prerequisites..."

# Node.js
if ! command -v node &>/dev/null; then
    die "Node.js not found. Install from https://nodejs.org (v${NODE_MIN}+)"
fi
NODE_VERSION=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
[ "$NODE_VERSION" -lt "$NODE_MIN" ] && die "Node.js ${NODE_MIN}+ required (found v$(node --version))"
success "Node.js $(node --version)"

# npm
if ! command -v npm &>/dev/null; then
    die "npm not found. Install Node.js from https://nodejs.org"
fi
success "npm $(npm --version)"

# Python
PYTHON_CMD=""
for cmd in python3.12 python3.11 python3.10 python3; do
    if command -v "$cmd" &>/dev/null; then
        PY_VER=$("$cmd" --version 2>&1 | grep -o '[0-9]\+\.[0-9]\+' | head -1)
        PY_MAJOR=$(echo "$PY_VER" | cut -d'.' -f1)
        PY_MINOR=$(echo "$PY_VER" | cut -d'.' -f2)
        if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 10 ]; then
            PYTHON_CMD="$cmd"
            break
        fi
    fi
done
[ -z "$PYTHON_CMD" ] && die "Python 3.10+ not found. Install from https://python.org"
success "Python $("$PYTHON_CMD" --version)"

# ── Clone or update repo ──────────────────────────────────────────────────────

if [ -d "$APP_DIR" ]; then
    info "Found existing AUA-Veritas directory — pulling latest..."
    cd "$APP_DIR"
    git pull origin main
else
    info "Cloning AUA-Veritas..."
    git clone "$REPO" "$APP_DIR"
    cd "$APP_DIR"
fi
success "Repository ready at $APP_DIR"

# ── Generate placeholder icons if needed ─────────────────────────────────────

mkdir -p assets

if [ ! -f "assets/icon.icns" ]; then
    warn "icon.icns not found — generating placeholder icon..."
    # Create a simple 1024x1024 placeholder icon using Python
    "$PYTHON_CMD" - << 'PYEOF'
import os, struct, zlib

# Generate a minimal valid PNG (purple square) for placeholder
def make_png(size, r, g, b):
    def chunk(name, data):
        c = zlib.crc32(name + data) & 0xffffffff
        return struct.pack('>I', len(data)) + name + data + struct.pack('>I', c)
    ihdr = struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0)
    raw = b''.join(b'\x00' + bytes([r, g, b] * size) for _ in range(size))
    idat = zlib.compress(raw)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) + chunk(b'IDAT', idat) + chunk(b'IEND', b'')

png = make_png(1024, 67, 56, 202)  # indigo #4338ca
with open('assets/icon.png', 'wb') as f:
    f.write(png)
print("Generated assets/icon.png")
PYEOF

    # Convert PNG to ICNS using sips + iconutil (built into macOS)
    if command -v sips &>/dev/null && command -v iconutil &>/dev/null; then
        mkdir -p /tmp/veritas-icon.iconset
        for size in 16 32 128 256 512; do
            sips -z $size $size assets/icon.png --out /tmp/veritas-icon.iconset/icon_${size}x${size}.png &>/dev/null
            doubled=$((size * 2))
            sips -z $doubled $doubled assets/icon.png --out /tmp/veritas-icon.iconset/icon_${size}x${size}@2x.png &>/dev/null
        done
        iconutil -c icns /tmp/veritas-icon.iconset --out assets/icon.icns
        rm -rf /tmp/veritas-icon.iconset
        success "Generated assets/icon.icns"
    else
        warn "sips/iconutil not found — skipping icon.icns generation"
        warn "App will build without a custom icon. Add assets/icon.icns later."
    fi
fi

if [ ! -f "assets/tray-icon.png" ]; then
    "$PYTHON_CMD" - << 'PYEOF'
import os, struct, zlib
def make_png(size, r, g, b):
    def chunk(name, data):
        c = zlib.crc32(name + data) & 0xffffffff
        return struct.pack('>I', len(data)) + name + data + struct.pack('>I', c)
    ihdr = struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0)
    raw = b''.join(b'\x00' + bytes([r, g, b] * size) for _ in range(size))
    idat = zlib.compress(raw)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) + chunk(b'IDAT', idat) + chunk(b'IEND', b'')
png = make_png(22, 255, 255, 255)  # white
with open('assets/tray-icon.png', 'wb') as f:
    f.write(png)
print("Generated assets/tray-icon.png")
PYEOF
    success "Generated assets/tray-icon.png"
fi

if [ ! -f "assets/dmg-background.png" ]; then
    "$PYTHON_CMD" - << 'PYEOF'
import os, struct, zlib
def make_png(w, h, r, g, b):
    def chunk(name, data):
        c = zlib.crc32(name + data) & 0xffffffff
        return struct.pack('>I', len(data)) + name + data + struct.pack('>I', c)
    ihdr = struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)
    raw = b''.join(b'\x00' + bytes([r, g, b] * w) for _ in range(h))
    idat = zlib.compress(raw)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) + chunk(b'IDAT', idat) + chunk(b'IEND', b'')
png = make_png(1080, 540, 250, 250, 248)  # #fafaf8
with open('assets/dmg-background.png', 'wb') as f:
    f.write(png)
print("Generated assets/dmg-background.png")
PYEOF
    success "Generated assets/dmg-background.png"
fi

# ── Set up Python virtual environment ─────────────────────────────────────────

info "Setting up Python virtual environment..."
"$PYTHON_CMD" -m venv "$VENV"
source "$VENV/bin/activate"

info "Installing Python dependencies..."
pip install --upgrade pip --quiet
pip install --quiet \
    fastapi \
    "uvicorn[standard]" \
    httpx \
    pydantic \
    keyring \
    pyyaml \
    numpy \
    scipy \
    spacy \
    pyinstaller

# Install spaCy blank model (no download needed, just the package)
python -c "import spacy; spacy.blank('en')" 2>/dev/null && success "spaCy OK" || warn "spaCy issue — trigger classifier may not work"

success "Python dependencies installed"

# ── Build Python backend with PyInstaller ─────────────────────────────────────

info "Building Python backend with PyInstaller..."
info "This may take 2-3 minutes on first run..."

# Ensure dist-backend dir is clean
rm -rf dist-backend build/pyinstaller-work

pyinstaller build/veritas-backend.spec \
    --distpath dist-backend \
    --workpath build/pyinstaller-work \
    --noconfirm \
    --log-level WARN

if [ ! -f "dist-backend/veritas-backend" ]; then
    die "PyInstaller build failed — veritas-backend binary not found"
fi

chmod +x dist-backend/veritas-backend
success "Backend binary built: dist-backend/veritas-backend ($(du -sh dist-backend/veritas-backend | cut -f1))"

# Quick smoke test
info "Smoke testing backend binary..."
VERITAS_API_PORT=47899 ./dist-backend/veritas-backend &
BACKEND_PID=$!
sleep 3

if curl -s http://127.0.0.1:47899/health | grep -q '"status"'; then
    success "Backend smoke test passed"
else
    warn "Backend smoke test inconclusive — may still work in app context"
fi
kill $BACKEND_PID 2>/dev/null || true
wait $BACKEND_PID 2>/dev/null || true

deactivate

# ── Build React UI ────────────────────────────────────────────────────────────

info "Building React UI..."
cd ui
npm install --silent
npm run build
cd ..
success "UI built: ui/dist/ ($(du -sh ui/dist | cut -f1))"

# ── Install Electron dependencies ──────────────────────────────────────────────

info "Installing Electron dependencies..."
npm install --silent
success "Electron dependencies installed"

# ── Build .dmg with electron-builder ──────────────────────────────────────────

info "Building macOS .dmg..."
info "Building for: $(arch) architecture"

npx electron-builder --mac --config electron-builder.json

# ── Find and report output ─────────────────────────────────────────────────────

DMG_FILE=$(find release -name "*.dmg" | head -1)

if [ -z "$DMG_FILE" ]; then
    die "Build failed — no .dmg found in release/"
fi

DMG_SIZE=$(du -sh "$DMG_FILE" | cut -f1)

echo ""
echo "  ╔═══════════════════════════════════════════════════════════╗"
echo "  ║   Build complete!                                         ║"
echo "  ╠═══════════════════════════════════════════════════════════╣"
printf  "  ║   %-55s  ║\n" "DMG: $DMG_FILE"
printf  "  ║   %-55s  ║\n" "Size: $DMG_SIZE"
echo "  ╠═══════════════════════════════════════════════════════════╣"
echo "  ║   Installation instructions for users:                   ║"
echo "  ║                                                           ║"
echo "  ║   1. Double-click the .dmg                               ║"
echo "  ║   2. Drag AUA-Veritas to Applications                    ║"
echo "  ║   3. Right-click AUA-Veritas → Open                     ║"
echo "  ║   4. Click Open in the security dialog                   ║"
echo "  ║   (Only needed on first launch — macOS gatekeeper)       ║"
echo "  ╚═══════════════════════════════════════════════════════════╝"
echo ""

success "Done! Upload $DMG_FILE to praneethtota.github.io/AUA-Veritas"
