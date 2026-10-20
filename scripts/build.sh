#!/usr/bin/env bash

set -eo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLEAN_FIRST=0

while (($# > 0)); do
    case "$1" in
    --clean | --clean-first)
        CLEAN_FIRST=1
        ;;
    -h | --help)
        echo "Usage: $0 [--clean]"
        echo
        echo "  --clean, --clean-first  Remove build/install/log before building"
        exit 0
        ;;
    *)
        echo "Unknown argument: $1" >&2
        exit 2
        ;;
    esac
    shift
done

source /opt/ros/jazzy/setup.bash

set -u

cd "$ROOT"

if ((CLEAN_FIRST)); then
    mkdir -p "$ROOT/build" "$ROOT/install" "$ROOT/log"
    shopt -s dotglob nullglob
    rm -rf "$ROOT"/build/* "$ROOT"/install/* "$ROOT"/log/*
    shopt -u dotglob nullglob
fi

PROJECT_PATHS=(
    src/mobile_bimanual_bringup
    src/mobile_bimanual_control
    src/mobile_bimanual_interfaces
    src/mobile_bimanual_description
    src/mobile_bimanual_sim
    src/mobile_bimanual_teleop
    src/mobile_bimanual_hardware
    src/openarm_description
    src/openarm_ros2/openarm_hardware
    src/openarm_ros2/openarm_bringup
    src/tracer_ros2/tracer_base
    src/tracer_ros2/tracer_msgs
    src/ugv_sdk
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
    --base-paths "${PROJECT_PATHS[@]}" \
    --symlink-install \
    --cmake-args -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
    --packages-select \
    openarm_description \
    openarm_hardware \
    openarm_bringup \
    mobile_bimanual_interfaces \
    mobile_bimanual_control \
    mobile_bimanual_bringup \
    mobile_bimanual_description \
    mobile_bimanual_sim \
    mobile_bimanual_teleop \
    mobile_bimanual_hardware \
    ugv_sdk \
    tracer_msgs \
    tracer_base

shopt -s nullglob
compile_databases=("$ROOT"/build/*/compile_commands.json)
if ((${#compile_databases[@]} > 0)); then
    jq -s 'add' "${compile_databases[@]}" >"$ROOT/compile_commands.json.tmp"
    mv "$ROOT/compile_commands.json.tmp" "$ROOT/compile_commands.json"
    echo "Generated $ROOT/compile_commands.json for clangd"
fi
