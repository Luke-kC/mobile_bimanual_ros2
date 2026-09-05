#!/usr/bin/env bash

set -euo pipefail

ROOT="/workspace"

cd "$ROOT"

echo "=== Preparing workspace build directories ==="

sudo mkdir -p \
    "$ROOT/build" \
    "$ROOT/install" \
    "$ROOT/log"

sudo chown -R \
    "$(id -u):$(id -g)" \
    "$ROOT/build" \
    "$ROOT/install" \
    "$ROOT/log"

echo "=== Importing locked upstream dependencies ==="
./scripts/import_upstream.sh

echo "=== Applying OpenArm source workarounds ==="

./scripts/patch_openarm_can20.sh
./scripts/patch_openarm_bringup.sh

echo "=== Updating apt package index ==="
sudo apt-get update

echo "=== Updating rosdep ==="
rosdep update

echo "=== Installing dependencies and building ==="
./scripts/build.sh

echo "=== Installing user development tools ==="

mkdir -p "$HOME/.local/bin"
touch "$HOME/.local/bin/env"

if ! command -v uv >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

export PATH="$HOME/.local/bin:$PATH"

uv tool install ruff || uv tool upgrade ruff
uv tool install ty || uv tool upgrade ty

echo
echo "Dev container setup complete."
