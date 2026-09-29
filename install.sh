#!/usr/bin/env bash
# ======================================================================
#   ULTRON — macOS / Linux Automated Installation Script
# ======================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "======================================================================"
echo "  ULTRON — CROSS-PLATFORM INSTALLATION"
echo "======================================================================"
echo ""

# Check Python 3
if command -v python3 >/dev/null 2>&1; then
    PY_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PY_CMD="python"
else
    echo "[!] Python 3 not detected."
    echo "[*] Please install Python 3 (3.10+) via brew, apt, or your package manager."
    exit 1
fi

echo "[*] Using Python: $($PY_CMD --version)"

# Create virtual environment
if [ ! -d ".venv" ]; then
    echo "[*] Creating virtual environment (.venv)..."
    $PY_CMD -m venv .venv
fi

VENV_PY=".venv/bin/python"
"$VENV_PY" -m pip install --upgrade pip setuptools wheel

# Install requirements
if [ -f "requirements.txt" ]; then
    echo "[*] Installing dependencies from requirements.txt..."
    "$VENV_PY" -m pip install -r requirements.txt
else
    echo "[*] Installing core dependencies..."
    "$VENV_PY" -m pip install fastapi uvicorn[standard] websockets pydantic httpx requests python-dotenv psutil
fi

# Build frontend if needed and node is present
if [ ! -f "frontend/dist/index.html" ] && command -v npm >/dev/null 2>&1; then
    echo "[*] Building frontend assets..."
    cd frontend && npm install && npm run build && cd ..
fi

# Create launch scripts
cat << 'EOF' > launch_ultron.sh
#!/usr/bin/env bash
cd "$(dirname "$0")"
.venv/bin/python desktop.py
EOF
chmod +x launch_ultron.sh

cat << 'EOF' > launch_cli.sh
#!/usr/bin/env bash
cd "$(dirname "$0")"
.venv/bin/python cli.py
EOF
chmod +x launch_cli.sh

echo ""
echo "======================================================================"
echo "  [SUCCESS] ULTRON Installation Complete!"
echo "======================================================================"
echo "  To launch Desktop GUI : ./launch_ultron.sh"
echo "  To launch Terminal CLI: ./launch_cli.sh"
echo "  Browser HUD           : http://localhost:8340"
echo "======================================================================"
