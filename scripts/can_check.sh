#!/usr/bin/env bash
set -euo pipefail
for iface in can0 can1; do
    echo "===== $iface ====="
    ip -details -statistics link show "$iface" || true
done
