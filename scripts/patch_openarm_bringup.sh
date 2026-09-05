#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PACKAGE_XML="$ROOT/src/openarm_ros2/openarm_bringup/package.xml"
OPENARM_ROOT="$ROOT/src/openarm_ros2"
RVIZ_PATCH="$ROOT/patches/openarm-optional-rviz.patch"

if [[ ! -f "$PACKAGE_XML" ]]; then
    echo "Missing: $PACKAGE_XML" >&2
    exit 1
fi

if grep -q \
    '<exec_depend>openarm_bimanual_moveit_config</exec_depend>' \
    "$PACKAGE_XML"; then
    sed -i \
        '/<exec_depend>openarm_bimanual_moveit_config<\/exec_depend>/d' \
        "$PACKAGE_XML"

    echo "Removed unused MoveIt dependency from openarm_bringup"
else
    echo "MoveIt dependency already removed or upstream changed"
fi

if git -C "$OPENARM_ROOT" apply --check "$RVIZ_PATCH" 2>/dev/null; then
    git -C "$OPENARM_ROOT" apply "$RVIZ_PATCH"
    echo "Made RViz optional in the OpenArm bimanual launch"
elif git -C "$OPENARM_ROOT" apply --reverse --check "$RVIZ_PATCH" 2>/dev/null; then
    echo "Optional RViz patch already applied"
else
    echo "OpenArm launch no longer matches $RVIZ_PATCH" >&2
    exit 1
fi
