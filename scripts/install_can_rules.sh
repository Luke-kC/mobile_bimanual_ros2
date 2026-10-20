#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="${REPO_ROOT}/config/can"

sudo install -m 0644 \
    "${CONFIG_DIR}/78-mobile-bimanual-can.rules" \
    /etc/udev/rules.d/

for file in "${CONFIG_DIR}"/*.link; do
    sudo install -m 0644 "$file" /etc/systemd/network/
done

sudo udevadm control --reload

echo "CAN rules installed. Reboot to apply interface naming."
