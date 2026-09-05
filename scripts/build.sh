#!/usr/bin/env bash

set -eo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

source /opt/ros/jazzy/setup.bash

set -u

cd "$ROOT"

PROJECT_PATHS=(
    src/mobile_bimanual_bringup
    src/mobile_bimanual_control
    src/mobile_bimanual_interfaces
    src/openarm_description
    src/openarm_ros2/openarm_hardware
    src/openarm_ros2/openarm_bringup
)

SKIP_ROSDEP_KEYS=(
    ament_python
    openarm_can
    zed_description
    ros_gz
    joint_state_publisher
    joint_state_publisher_gui
)

rosdep install \
    --from-paths "${PROJECT_PATHS[@]}" \
    --ignore-src \
    --skip-keys "${SKIP_ROSDEP_KEYS[*]}" \
    -r \
    -y

colcon build \
    --symlink-install \
    --cmake-args -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
    --packages-select \
    openarm_description \
    openarm_hardware \
    openarm_bringup \
    mobile_bimanual_interfaces \
    mobile_bimanual_control \
    mobile_bimanual_bringup

shopt -s nullglob
compile_databases=("$ROOT"/build/*/compile_commands.json)
if (( ${#compile_databases[@]} > 0 )); then
    jq -s 'add' "${compile_databases[@]}" >"$ROOT/compile_commands.json.tmp"
    mv "$ROOT/compile_commands.json.tmp" "$ROOT/compile_commands.json"
    echo "Generated $ROOT/compile_commands.json for clangd"
fi
