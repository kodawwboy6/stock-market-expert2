#!/usr/bin/env bash
# setup.sh — Install Stock Market Expert as a systemd service.
#
# Usage:
#   sudo ./systemd/setup.sh        # install for current user
#   sudo ./systemd/setup.sh --uninstall  # remove service
#
# Prerequisites:
#   - Python 3.11+ installed
#   - Virtual environment at .venv/
#   - .env file in project root
#   - systemd available on the system

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE_NAME="stock-market-expert"
SERVICE_FILE="systemd/${SERVICE_NAME}.service"
USER="${SUDO_USER:-$(whoami)}"

# ── Detect virtual env ──────────────────────────────────────────────

VENV_PYTHON=""
if [ -f "${PROJECT_DIR}/.venv/bin/python" ]; then
    VENV_PYTHON="${PROJECT_DIR}/.venv/bin/python"
elif command -v python3 &>/dev/null; then
    VENV_PYTHON="$(command -v python3)"
else
    echo "ERROR: No Python 3 found. Install Python 3.11+ and create a virtual environment."
    exit 1
fi

echo "Using Python: ${VENV_PYTHON}"
echo "Project directory: ${PROJECT_DIR}"

# ── Install ─────────────────────────────────────────────────────────

install_service() {
    echo "Installing systemd service..."

    # Create a drop-in override with user-specific paths
    sudo mkdir -p /etc/systemd/system/${SERVICE_NAME}.service.d
    cat | sudo tee /etc/systemd/system/${SERVICE_NAME}.service.d/override.conf >/dev/null <<OVERRIDE
[Service]
User=${USER}
WorkingDirectory=${PROJECT_DIR}
ExecStart=${VENV_PYTHON} ${PROJECT_DIR}/main.py
OVERRIDE

    # Reload systemd
    sudo systemctl daemon-reload

    # Enable and start
    sudo systemctl enable ${SERVICE_NAME}
    sudo systemctl start ${SERVICE_NAME}

    echo "Service installed and started."
    echo "Status: systemctl status ${SERVICE_NAME}"
    echo "Logs: journalctl -u ${SERVICE_NAME} -f"
}

# ── Uninstall ───────────────────────────────────────────────────────

uninstall_service() {
    echo "Uninstalling systemd service..."

    sudo systemctl stop ${SERVICE_NAME} 2>/dev/null || true
    sudo systemctl disable ${SERVICE_NAME} 2>/dev/null || true
    sudo systemctl daemon-reload

    sudo rm -f /etc/systemd/system/${SERVICE_NAME}.service
    sudo rm -rf /etc/systemd/system/${SERVICE_NAME}.service.d

    echo "Service uninstalled."
}

# ── Main ────────────────────────────────────────────────────────────

if [ "${1:-}" = "--uninstall" ]; then
    uninstall_service
else
    # Verify .env exists
    if [ ! -f "${PROJECT_DIR}/.env" ]; then
        echo "WARNING: .env not found at ${PROJECT_DIR}/.env"
        echo "Copy .env.example and fill in your API keys:"
        echo "  cp ${PROJECT_DIR}/.env.example ${PROJECT_DIR}/.env"
    fi

    install_service
fi
