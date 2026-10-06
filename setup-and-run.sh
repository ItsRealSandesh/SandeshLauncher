#!/usr/bin/env bash
# ==============================================================================
# SANDESHLAUNCHER - Linux (Debian 13+) One-Click Setup & Launch Script
# ==============================================================================
set -e

# Terminal colors
BOLD='\033[1m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${CYAN}${BOLD}"
echo "=========================================================="
echo "          SANDESHLAUNCHER - Production Launcher           "
echo "=========================================================="
echo -e "${NC}"

# 1. Detect Python 3
echo -e "${CYAN}[1/5] Checking Python 3 installation...${NC}"
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}[ERROR] Python 3 is not installed on this system.${NC}"
    echo -e "On Debian / Ubuntu, please install it via:"
    echo -e "  sudo apt update && sudo apt install -y python3 python3-pip python3-venv python3-tk"
    exit 1
fi

PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo -e "${GREEN}✓ Found Python ${PY_VER}${NC}"

# 2. Check Tkinter
echo -e "${CYAN}[2/5] Checking GUI environment (Tkinter)...${NC}"
if ! python3 -c "import tkinter" &>/dev/null; then
    echo -e "${YELLOW}[WARNING] python3-tk is not installed.${NC}"
    echo -e "On Debian / Ubuntu, please run:"
    echo -e "  sudo apt update && sudo apt install -y python3-tk"
    echo -e "Attempting to continue, but GUI may fail if tkinter is missing."
fi

# 3. Virtual Environment Setup
VENV_DIR="$SCRIPT_DIR/.venv"
echo -e "${CYAN}[3/5] Setting up environment...${NC}"

HAS_VENV=0
if [ -d "$VENV_DIR" ] && [ -f "$VENV_DIR/bin/activate" ]; then
    source "$VENV_DIR/bin/activate"
    HAS_VENV=1
else
    if python3 -m venv "$VENV_DIR" 2>/dev/null; then
        source "$VENV_DIR/bin/activate"
        HAS_VENV=1
    else
        echo -e "${YELLOW}[NOTE] python3-venv package not found; checking system packages...${NC}"
    fi
fi

# 4. Install / Verify Requirements
echo -e "${CYAN}[4/5] Checking dependencies...${NC}"
if python3 -c "import customtkinter, minecraft_launcher_lib, PIL, requests, packaging, psutil, keyring, cryptography" 2>/dev/null; then
    echo -e "${GREEN}✓ All core dependencies are satisfied!${NC}"
else
    echo -e "Installing dependencies from requirements.txt..."
    if [ "$HAS_VENV" -eq 1 ]; then
        pip install --upgrade pip >/dev/null 2>&1 || true
        pip install -r requirements.txt
    else
        pip install -r requirements.txt --break-system-packages 2>/dev/null || pip install -r requirements.txt || true
    fi
fi

# 5. Launch SandeshLauncher
echo -e "${GREEN}${BOLD}[5/5] Launching SandeshLauncher...${NC}"
echo "=========================================================="
exec python3 launcher.py "$@"
