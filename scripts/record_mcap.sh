#!/usr/bin/env bash
set -euo pipefail

OUT="${1:-bags/$(date +%Y%m%d_%H%M%S)}"

mkdir -p "$(dirname "$OUT")"

echo "Recording MCAP to: $OUT"

ros2 bag record \
    -s mcap \
    -o "$OUT" \
    --regex '^(/joint_states|/dynamic_joint_states|/tf|/tf_static|/robot_description|/mobile_bimanual/joint_targets|/left_forward_position_controller/commands|/right_forward_position_controller/commands|/openarm_named_joint_states/.*)$'
