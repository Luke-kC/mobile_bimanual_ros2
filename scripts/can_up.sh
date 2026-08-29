#!/usr/bin/env bash
set -euo pipefail

configure_can20() {
    local iface="$1"
    if ! ip link show "$iface" >/dev/null 2>&1; then
        echo "ERROR: $iface not found" >&2
        return 1
    fi

    sudo ip link set "$iface" down || true
    sudo ip link set "$iface" type can fd off
    sudo ip link set "$iface" mtu 16
    sudo ip link set "$iface" type can bitrate 1000000 restart-ms 100
    sudo ip link set "$iface" up
}

configure_can20 can0
configure_can20 can1

ip -details link show can0
ip -details link show can1
