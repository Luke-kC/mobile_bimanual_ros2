#!/usr/bin/env bash

set -euo pipefail

CONTAINER_NAME="${ROS_CONTAINER:-mobile-bimanual-ros2-linux-nvidia}"

if [[ $# -eq 0 ]]; then
    cat >&2 <<EOF
Usage: $0 <command> [args...]

Examples:
  $0 ros2 node list
  $0 ros2 topic info /robot_description --verbose
  $0 ros2 control list_controllers -c /leader/controller_manager

Override the container name with:
  ROS_CONTAINER=<container_name> $0 ros2 node list
EOF
    exit 2
fi

if ! docker ps --format '{{.Names}}' | grep -Fxq "$CONTAINER_NAME"; then
    echo "Container is not running: $CONTAINER_NAME" >&2
    echo "Running containers:" >&2
    docker ps --format 'table {{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Status}}' >&2
    exit 1
fi

docker exec "$CONTAINER_NAME" bash -lc '
    source /opt/ros/jazzy/setup.bash
    source /workspace/install/setup.bash
    exec "$@"
' bash "$@"
