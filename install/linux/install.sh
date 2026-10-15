#!/usr/bin/env bash
# Dependencias del sistema + venv Python (Debian/Ubuntu). Ajuste el gestor si usa otra distro.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if command -v apt-get >/dev/null 2>&1; then
  echo "Instalando paquetes del sistema (puede pedir sudo)…"
  sudo apt-get update
  sudo apt-get install -y \
    python3 python3-venv python3-tk \
    sane-utils libsane1 \
    cups cups-client
else
  echo "Instale manualmente: python3, python3-tk, venv, sane-utils, cups-client"
fi

python3 -m venv venv
# shellcheck disable=SC1091
source venv/bin/activate
pip install -U pip
pip install -r requirements.txt

DESKTOP="$ROOT/install/linux/printer-scanner-manager.desktop"
sed "s|@APP_ROOT@|$ROOT|g" "$DESKTOP.in" > "$HOME/.local/share/applications/printer-scanner-manager.desktop"
chmod +x "$ROOT/install/linux/run.sh"
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

echo ""
echo "Listo. Ejecute: $ROOT/install/linux/run.sh"
echo "O: source venv/bin/activate && python main.py"
