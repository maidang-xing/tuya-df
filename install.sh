#!/usr/bin/env bash
# tuya-df — one-click installer
# Usage: curl -sSL https://raw.githubusercontent.com/maidang-xing/tuya-df/main/install.sh | bash
set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BOLD}tuya-df installer${NC}"
echo ""

# ---- Detect pipx (preferred) vs pip ----
if command -v pipx &>/dev/null; then
    INSTALLER="pipx"
elif command -v pip3 &>/dev/null; then
    INSTALLER="pip3"
else
    echo -e "${RED}Error: Neither pipx nor pip3 found. Install Python 3.9+ first.${NC}"
    exit 1
fi

# ---- Install tuya-df ----
echo -e "${YELLOW}Installing tuya-df via ${INSTALLER}...${NC}"
if [ "$INSTALLER" = "pipx" ]; then
    pipx install "git+https://github.com/maidang-xing/tuya-df.git"
    pipx inject tuya-df playwright
else
    pip3 install --user "git+https://github.com/maidang-xing/tuya-df.git" playwright
    # Ensure user bin is in PATH
    PYTHON_BIN="$(python3 -m site --user-base)/bin"
    if [[ ":$PATH:" != *":$PYTHON_BIN:"* ]]; then
        echo -e "${YELLOW}⚠️  Add $PYTHON_BIN to your PATH:${NC}"
        echo "    export PATH=\"$PYTHON_BIN:\$PATH\""
    fi
fi

# ---- Install Playwright Chromium (for browser login) ----
echo -e "${YELLOW}Installing Chromium for browser login...${NC}"
if [ "$INSTALLER" = "pipx" ]; then
    pipx run --spec tuya-df python -m playwright install chromium 2>/dev/null || \
    ~/.local/share/pipx/venvs/tuya-df/bin/python -m playwright install chromium
else
    python3 -m playwright install chromium
fi

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
    echo -e "${YELLOW}⚠️  tuya-df not found in PATH. Try opening a new terminal.${NC}"
    echo "   Or run: export PATH=\"~/.local/bin:\$PATH\""
fi
