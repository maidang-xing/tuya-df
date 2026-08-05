#!/usr/bin/env bash
# tuya-df — Cross-platform installer for Linux and macOS
# Usage: curl -sSL https://raw.githubusercontent.com/maidang-xing/tuya-df/main/install.sh | bash
set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BOLD}tuya-df installer (Linux / macOS)${NC}"
echo ""

# ---- Detect OS ----
OS="$(uname -s)"
case "$OS" in
    Linux*)  PLATFORM="linux" ;;
    Darwin*) PLATFORM="macos" ;;
    *)       echo -e "${RED}Unsupported OS: $OS${NC}"; exit 1 ;;
esac
echo -e "Platform: ${PLATFORM}"

# ---- Ensure Python 3.9+ ----
if ! command -v python3 &>/dev/null; then
    echo -e "${YELLOW}Python 3 not found. Installing...${NC}"
    if [ "$PLATFORM" = "macos" ]; then
        if ! command -v brew &>/dev/null; then
            echo -e "${RED}Homebrew not found. Install it: https://brew.sh${NC}"
            echo -e "${YELLOW}Or install Xcode Command Line Tools: xcode-select --install${NC}"
            exit 1
        fi
        brew install python@3.12
    else
        echo -e "${RED}Please install Python 3.9+ first:${NC}"
        echo "  Ubuntu/Debian: sudo apt install python3 python3-pip python3-venv"
        echo "  Fedora:        sudo dnf install python3 python3-pip"
        echo "  Arch:          sudo pacman -S python python-pip"
        exit 1
    fi
fi

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')
echo -e "Python: $PY_VERSION"

# ---- Ensure pipx (preferred) ----
if ! command -v pipx &>/dev/null; then
    echo -e "${YELLOW}pipx not found. Installing...${NC}"
    if [ "$PLATFORM" = "macos" ] && command -v brew &>/dev/null; then
        brew install pipx
    else
        python3 -m pip install --user pipx 2>/dev/null || python3 -m ensurepip --user
        python3 -m pip install --user pipx
    fi
    pipx ensurepath 2>/dev/null || true
    export PATH="$HOME/.local/bin:$PATH"
fi

# ---- Install tuya-df ----
echo ""
echo -e "${YELLOW}Installing tuya-df...${NC}"
pipx install "git+https://github.com/maidang-xing/tuya-df.git"
pipx inject tuya-df playwright

# ---- Install Chromium for browser login ----
echo ""
echo -e "${YELLOW}Installing Chromium for browser login...${NC}"
~/.local/share/pipx/venvs/tuya-df/bin/python -m playwright install chromium 2>/dev/null || \
    python3 -m playwright install chromium

# ---- Install Claude Code skill (if Claude Code is detected) ----
SKILL_SRC="/tmp/tuya-df-skill"
if [ ! -d "$SKILL_SRC" ]; then
    git clone --depth 1 https://github.com/maidang-xing/tuya-df.git "$SKILL_SRC" 2>/dev/null || true
fi

if [ -d "$SKILL_SRC/.claude/skills/tuya-df" ]; then
    if [ -d "$HOME/.claude/skills" ] || command -v claude &>/dev/null; then
        echo ""
        echo -e "${YELLOW}Installing Claude Code skill...${NC}"
        mkdir -p "$HOME/.claude/skills"
        cp -r "$SKILL_SRC/.claude/skills/tuya-df" "$HOME/.claude/skills/"
        echo -e "${GREEN}✅ Skill installed to ~/.claude/skills/tuya-df/${NC}"
    fi
fi
rm -rf "$SKILL_SRC"

# ---- Verify ----
echo ""
if command -v tuya-df &>/dev/null; then
    echo -e "${GREEN}✅ tuya-df installed successfully!${NC}"
    tuya-df --version
    echo ""
    echo -e "${BOLD}Next steps:${NC}"
    echo "  tuya-df auth login      # Log in to the forum (opens browser)"
    echo "  tuya-df categories      # See forum categories"
    echo "  tuya-df post create --title \"Hello\" --body \"World\" -c show-tell"
else
    echo -e "${YELLOW}⚠️  tuya-df not found in PATH. Open a new terminal or run:${NC}"
    echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
fi
