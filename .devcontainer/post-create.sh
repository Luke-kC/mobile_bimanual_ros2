#!/usr/bin/env bash

set -euo pipefail

ROOT="/workspace"

cd "$ROOT"

echo "=== Importing locked upstream dependencies ==="
./scripts/import_upstream.sh

echo "=== Applying OpenArm CAN 2.0 workaround ==="
./scripts/patch_openarm_can20.sh

echo "=== Updating rosdep ==="
rosdep update

echo "=== Installing project ROS dependencies and building ==="
./scripts/build.sh

echo "=== Installing user development tools ==="

if ! command -v uv >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

export PATH="$HOME/.local/bin:$PATH"

uv tool install ruff@latest || uv tool upgrade ruff
uv tool install ty@latest || uv tool upgrade ty

echo
echo "Dev container setup complete."
echo "Open a new shell so workspace setup.zsh is sourced."
