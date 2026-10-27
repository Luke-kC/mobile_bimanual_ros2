#!/usr/bin/env bash
set -euo pipefail

# Camera udev rules must be installed on the host, not inside Docker.
if [[ -f /.dockerenv ]]; then
    echo "ERROR: Run this script on the host, not inside the devcontainer." >&2
    exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="${REPO_ROOT}/config/camera_udev"

sudo install -m 0644 \
    "${CONFIG_DIR}/80-movidius.rules" \
    /etc/udev/rules.d/

sudo install -m 0644 \
    "${CONFIG_DIR}/99-realsense-libusb.rules" \
    /etc/udev/rules.d/

sudo udevadm control --reload-rules

echo "Camera udev rules installed."
echo "Unplug and reconnect the OAK-D Pro and RealSense cameras."
