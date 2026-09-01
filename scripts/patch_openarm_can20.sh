#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

backup_once() {
    local f="$1"
    if [[ ! -f "$f.bak" ]]; then
        cp "$f" "$f.bak"
    fi
}

files=(
    "$ROOT/src/openarm_description/assets/robot/openarm_v2.0/urdf/ros2_control/openarm.bimanual.ros2_control.xacro"
    "$ROOT/src/openarm_description/assets/robot/openarm_v1.0/urdf/ros2_control/openarm.bimanual.ros2_control.xacro"
    "$ROOT/src/openarm_description/assets/robot/openarm_v1.0/urdf/ros2_control/openarm.ros2_control.xacro"
)

for f in "${files[@]}"; do
    if [[ ! -f "$f" ]]; then
        echo "Skipping missing file: $f"
        continue
    fi
    if grep -q 'can_fd:=\^|true' "$f"; then
        backup_once "$f"
        sed -i 's/can_fd:=\^|true/can_fd:=^|false/' "$f"
        echo "Patched CAN-FD default to false: $f"
    elif grep -q 'can_fd:=\^|false' "$f"; then
        echo "CAN-FD default already false: $f"
    else
        echo "No matching true default found; inspect manually: $f"
    fi
done

v1_top="$ROOT/src/openarm_description/assets/robot/openarm_v1.0/urdf/openarm_v10.urdf.xacro"
if [[ -f "$v1_top" ]]; then
    if grep -q '<xacro:arg name="can_fd" default="true" />' "$v1_top"; then
        backup_once "$v1_top"
        sed -i 's/<xacro:arg name="can_fd" default="true" \/>/<xacro:arg name="can_fd" default="false" \/>/' "$v1_top"
        echo "Patched V1 top-level CAN-FD default to false: $v1_top"
    elif grep -q '<xacro:arg name="can_fd" default="false" />' "$v1_top"; then
        echo "V1 top-level CAN-FD default already false: $v1_top"
    else
        echo "No V1 top-level true default found; inspect manually: $v1_top"
    fi
else
    echo "Skipping missing file: $v1_top"
fi

v1_robot="$ROOT/src/openarm_description/assets/robot/openarm_v1.0/urdf/robot/openarm_robot.xacro"
if [[ -f "$v1_robot" ]]; then
    if perl -0ne 'exit(/hand="true"\n\s*ee_type="\$\{ee_type\}"\/>/ ? 0 : 1)' "$v1_robot"; then
        backup_once "$v1_robot"
        perl -0pi -e 's/hand="true"\n(\s*)ee_type="\$\{ee_type\}"\/>/hand="true"\n${1}can_fd="\${can_fd}"\n${1}ee_type="\${ee_type}"\/>/g' "$v1_robot"
        echo "Patched V1 bimanual CAN-FD forwarding: $v1_robot"
    elif perl -0ne 'exit(/hand="true"\n\s*can_fd="\$\{can_fd\}"\n\s*ee_type="\$\{ee_type\}"\/>/ ? 0 : 1)' "$v1_robot"; then
        echo "V1 bimanual CAN-FD forwarding already present: $v1_robot"
    else
        echo "Could not find V1 bimanual forwarding insertion point; inspect manually: $v1_robot"
    fi
else
    echo "Skipping missing file: $v1_robot"
fi

echo "This is a temporary workaround for classic CAN 2.0. Re-check upstream before each dependency update."
