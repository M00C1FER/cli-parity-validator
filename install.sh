#!/usr/bin/env bash
# CLI Parity Validator — install wizard
# Supports: Linux, WSL, Termux (Android)
set -euo pipefail

BLUE='\033[0;34m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERR]${NC}   $*"; exit 1; }
prompt()  { echo -e "${YELLOW}[INPUT]${NC} $*"; }

detect_platform() {
    if [ -n "${TERMUX_VERSION:-}" ] || [ -d "/data/data/com.termux" ]; then echo "termux"
    elif grep -qi microsoft /proc/version 2>/dev/null; then echo "wsl"
    else echo "linux"; fi
}

detect_pkg_manager() {
    if command -v apt-get &>/dev/null; then echo "apt"
    elif command -v dnf &>/dev/null; then echo "dnf"
    elif command -v pacman &>/dev/null; then echo "pacman"
    elif command -v apk &>/dev/null; then echo "apk"
    else echo "unknown"; fi
}

install_deps_system() {
    local plat="$1"
    info "Installing system dependencies ($plat)..."
    case "$plat" in
        termux)
            pkg update -y
            pkg install -y python git
            ;;
        wsl|linux)
            local pm
            pm=$(detect_pkg_manager)
            case "$pm" in
                apt)
                    sudo apt-get update -qq
                    sudo apt-get install -y python3 python3-venv python3-pip git
                    ;;
                dnf)
                    sudo dnf install -y python3 python3-virtualenv git
                    ;;
                pacman)
                    sudo pacman -Sy --noconfirm python git
                    ;;
                apk)
                    # Alpine Linux — py3-pip ships a venv-capable pip
                    sudo apk update
                    sudo apk add --no-cache python3 py3-pip git
                    ;;
                *)
                    warn "Unknown package manager — ensure python3, pip, and git are installed"
                    ;;
            esac
            ;;
    esac
}

PLATFORM=$(detect_platform)
INSTALL_DIR="${HOME}/.local/share/cli-parity-validator"
VENV_DIR="${INSTALL_DIR}/.venv"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║      CLI Parity Validator  v1.0.0        ║"
echo "║  Validate AI CLI toolset consistency     ║"
echo "╚══════════════════════════════════════════╝"
echo ""
info "Platform detected: $PLATFORM"

install_deps_system "$PLATFORM"

info "Creating virtual environment at $VENV_DIR"
mkdir -p "$INSTALL_DIR"
if [ "$PLATFORM" = "termux" ]; then
    python -m venv "$VENV_DIR"
else
    python3 -m venv "$VENV_DIR"
fi

info "Activating environment and installing package..."
"$VENV_DIR/bin/pip" install --upgrade pip -q
"$VENV_DIR/bin/pip" install . -q

# --- Credential Wizard ---
echo ""
echo "─────────────────────────────────────────────"
echo " Optional Credential Configuration"
echo " These are only needed for advanced features."
echo "─────────────────────────────────────────────"

ENV_FILE="${INSTALL_DIR}/.env"
touch "$ENV_FILE"
chmod 600 "$ENV_FILE"
if ! grep -q "VALIDATOR_SCHEMA_PATH" "$ENV_FILE" 2>/dev/null; then
    echo "" >> "$ENV_FILE"
    echo "# CLI Parity Validator configuration" >> "$ENV_FILE"
fi

prompt "Enter path to your MCP server tool schema YAML (leave blank to skip):"
read -r schema_path
if [ -n "$schema_path" ]; then
    echo "VALIDATOR_SCHEMA_PATH=${schema_path}" >> "$ENV_FILE"
fi

prompt "Enter path to agent-tools directory (leave blank to skip):"
read -r agent_tools_path
if [ -n "$agent_tools_path" ]; then
    echo "VALIDATOR_AGENT_TOOLS_DIR=${agent_tools_path}" >> "$ENV_FILE"
fi

success "Credentials saved to $ENV_FILE (chmod 600, never committed)"

# --- Wrapper script ---
WRAPPER="${HOME}/.local/bin/cli-parity"
mkdir -p "$(dirname "$WRAPPER")"
cat > "$WRAPPER" << WRAPEOF
#!/usr/bin/env bash
set -a; [ -f "${ENV_FILE}" ] && . "${ENV_FILE}"; set +a
exec "${VENV_DIR}/bin/cli-parity" "\$@"
WRAPEOF
chmod +x "$WRAPPER"

echo ""
success "Installation complete!"
echo ""
echo "  Usage:  cli-parity --help"
echo "  Config: $ENV_FILE"
echo "  Docs:   https://github.com/M00C1FER/cli-parity-validator"
echo ""
echo "  Quick start:"
echo "    cli-parity --schema schema.yaml --strict"
