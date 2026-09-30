#!/usr/bin/env bash
# ======================================================================
#   ULTRON -- Official macOS & Linux 1-Line Web Installer
#   Usage: curl -fsSL https://raw.githubusercontent.com/Yeezie08147/ultron/main/install.sh | bash
# ======================================================================

set -e

# Terminal Colors
ORANGE='\033[38;5;208m'
CYAN='\033[36m'
GREEN='\033[32m'
YELLOW='\033[33m'
RED='\033[31m'
BOLD='\033[1m'
RESET='\033[0m'

echo -e "${ORANGE}${BOLD}"
echo "======================================================================"
echo "   ULTRON // OFFICIAL macOS CLI INSTALLER // AUTONOMOUS MATRIX"
echo "======================================================================"
echo -e "${RESET}"

INSTALL_DIR="$HOME/.ultron"
BIN_DIR="$INSTALL_DIR/bin"
REPO_URL="https://github.com/Yeezie08147/ultron.git"
ZIP_URL="https://github.com/Yeezie08147/ultron/archive/refs/heads/main.zip"

echo -e "${CYAN}[*] Target Installation Directory:${RESET} $INSTALL_DIR"

# -- Step 1: Detect OS & Architecture --
OS_TYPE="$(uname -s)"
ARCH_TYPE="$(uname -m)"
echo -e "${CYAN}[1/6] System Platform:${RESET} $OS_TYPE ($ARCH_TYPE)"

# -- Step 2: Check Python Runtime --
echo -e "${CYAN}[2/6] Checking Python 3 runtime...${RESET}"
PYTHON_BIN=""

if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
fi

# If Python is missing or too old, attempt Homebrew install on macOS
if [ -z "$PYTHON_BIN" ]; then
    if [ "$OS_TYPE" = "Darwin" ] && command -v brew >/dev/null 2>&1; then
        echo -e "${YELLOW}[!] Python3 missing. Installing via Homebrew...${RESET}"
        brew install python@3.12
        PYTHON_BIN="python3"
    fi
fi

if [ -z "$PYTHON_BIN" ]; then
    echo -e "${RED}[ERROR] Python 3.10+ is required to run ULTRON.${RESET}"
    echo -e "${YELLOW}Install Python via Homebrew: brew install python@3.12${RESET}"
    exit 1
fi

PY_VER=$($PYTHON_BIN --version 2>&1)
echo -e "${GREEN}[OK] Python detected:${RESET} $PY_VER"

# -- Step 3: Fetch or Update ULTRON Repository --
echo -e "${CYAN}[3/6] Fetching ULTRON repository into $INSTALL_DIR...${RESET}"
if [ -d "$INSTALL_DIR" ]; then
    if [ -d "$INSTALL_DIR/.git" ]; then
        echo -e "${CYAN}[*] Updating existing Git repository...${RESET}"
        git -C "$INSTALL_DIR" pull origin main || true
    else
        echo -e "${YELLOW}[*] Existing directory found. Refreshing files...${RESET}"
    fi
else
    mkdir -p "$INSTALL_DIR"
    if command -v git >/dev/null 2>&1; then
        echo -e "${CYAN}[*] Cloning with Git...${RESET}"
        git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
    else
        echo -e "${CYAN}[*] Git not detected. Downloading package zip...${RESET}"
        TEMP_ZIP="/tmp/ultron_install.zip"
        TEMP_EXT="/tmp/ultron_extract"
        curl -fsSL "$ZIP_URL" -o "$TEMP_ZIP"
        rm -rf "$TEMP_EXT"
        mkdir -p "$TEMP_EXT"
        unzip -q "$TEMP_ZIP" -d "$TEMP_EXT"
        cp -R "$TEMP_EXT/ultron-main/"* "$INSTALL_DIR/"
        rm -f "$TEMP_ZIP"
        rm -rf "$TEMP_EXT"
    fi
fi

# -- Step 4: Configure Virtual Environment --
echo -e "${CYAN}[4/6] Configuring virtual environment (.venv)...${RESET}"
VENV_DIR="$INSTALL_DIR/.venv"
VENV_PY="$VENV_DIR/bin/python3"

if [ ! -f "$VENV_PY" ]; then
    $PYTHON_BIN -m venv "$VENV_DIR"
fi

echo -e "${CYAN}[5/6] Installing dependencies from requirements.txt...${RESET}"
"$VENV_PY" -m pip install --upgrade pip setuptools wheel --quiet
if [ -f "$INSTALL_DIR/requirements.txt" ]; then
    "$VENV_PY" -m pip install -r "$INSTALL_DIR/requirements.txt" --quiet
fi

# Optional ADB check / install via Homebrew on macOS
if [ "$OS_TYPE" = "Darwin" ] && command -v brew >/dev/null 2>&1; then
    if ! command -v adb >/dev/null 2>&1; then
        echo -e "${CYAN}[*] Installing Android Debug Bridge (ADB) via Homebrew...${RESET}"
        brew install android-platform-tools || true
    fi
fi

# Optional frontend dashboard build if npm is present
if command -v npm >/dev/null 2>&1 && [ -f "$INSTALL_DIR/frontend/package.json" ]; then
    echo -e "${CYAN}[*] Building web dashboard assets...${RESET}"
    (cd "$INSTALL_DIR/frontend" && npm install --silent && npm run build --silent) || true
fi

# -- Step 5: Register Global Executable Shim --
echo -e "${CYAN}[6/6] Registering global ultron command...${RESET}"
mkdir -p "$BIN_DIR"
mkdir -p "$HOME/.local/bin"

SHIM_FILE="$BIN_DIR/ultron"
cat << 'EOF' > "$SHIM_FILE"
#!/usr/bin/env bash
export PYTHONIOENCODING=utf-8
INSTALL_DIR="$HOME/.ultron"
exec "$INSTALL_DIR/.venv/bin/python3" "$INSTALL_DIR/cli.py" "$@"
EOF

chmod +x "$SHIM_FILE"
cp -f "$SHIM_FILE" "$HOME/.local/bin/ultron" 2>/dev/null || true

# Try symlink in /usr/local/bin if writable
if [ -w "/usr/local/bin" ]; then
    ln -sf "$SHIM_FILE" "/usr/local/bin/ultron"
fi

# Ensure ~/.local/bin and ~/.ultron/bin are in shell PATH
SHELL_PROFILES=("$HOME/.zshrc" "$HOME/.bash_profile" "$HOME/.bashrc")
PATH_EXPORT='export PATH="$HOME/.ultron/bin:$HOME/.local/bin:$PATH"'

for PROF in "${SHELL_PROFILES[@]}"; do
    if [ -f "$PROF" ]; then
        if ! grep -q "\.ultron/bin" "$PROF"; then
            echo "" >> "$PROF"
            echo "# ULTRON CLI PATH" >> "$PROF"
            echo "$PATH_EXPORT" >> "$PROF"
        fi
    fi
done

export PATH="$HOME/.ultron/bin:$HOME/.local/bin:$PATH"

echo -e "${GREEN}${BOLD}"
echo "======================================================================"
echo "   [SUCCESS] ULTRON CLI IS OFFICIALLY INSTALLED ON macOS!"
echo "======================================================================"
echo -e "${RESET}"
echo -e "You can now run ULTRON anywhere from Terminal or iTerm by typing:"
echo -e "  ${ORANGE}${BOLD}ultron${RESET}                  Launch Interactive Matrix REPL"
echo -e "  ${ORANGE}${BOLD}ultron /bridge${RESET}          Auto-bridge USB phone to Wi-Fi"
echo -e "  ${ORANGE}${BOLD}ultron /unlock${RESET}          Hands-free screen unlock"
echo -e "  ${ORANGE}${BOLD}ultron /wifi${RESET}            Check Wi-Fi interface & network state"
echo -e "  ${ORANGE}${BOLD}ultron /help${RESET}            Display Slash Command Directory"
echo ""
echo -e "${CYAN}If 'ultron' is not recognized immediately in your current terminal, reload your shell:${RESET}"
echo -e "  source ~/.zshrc"
echo ""
