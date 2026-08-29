#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

files=(
    "$ROOT/src/openarm_description/assets/robot/openarm_v2.0/urdf/ros2_control/openarm.bimanual.ros2_control.xacro"
    "$ROOT/src/openarm_description/assets/robot/openarm_v1.0/urdf/ros2_control/openarm.bimanual.ros2_control.xacro"
)

for f in "${files[@]}"; do
    if [[ ! -f "$f" ]]; then
        echo "Skipping missing file: $f"
        continue
    fi
    if grep -q 'can_fd:=\^|true' "$f"; then
        cp -n "$f" "$f.bak" || true
        sed -i 's/can_fd:=\^|true/can_fd:=^|false/' "$f"
        echo "Patched CAN-FD default to false: $f"
    else
        echo "No matching true default found; inspect manually: $f"
    fi
done

echo "This is a temporary workaround for classic CAN 2.0. Re-check upstream before each dependency update."
