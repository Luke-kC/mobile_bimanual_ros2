#!/usr/bin/env bash

set -eo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

source /opt/ros/jazzy/setup.bash

cd "$ROOT"

rosdep install \
    --from-paths src \
    --ignore-src \
    -r \
    -y

colcon build --symlink-install
