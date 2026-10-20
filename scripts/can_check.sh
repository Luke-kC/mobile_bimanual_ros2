#!/usr/bin/env bash
set -euo pipefail
for iface in can_arm_l can_arm_r can_tracer; do
    echo "===== $iface ====="
    ip -details -statistics link show "$iface" || true
done
