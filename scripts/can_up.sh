#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# CAN interfaces
# ---------------------------------------------------------------------------

OPENARM_RIGHT="can_arm_r"
OPENARM_LEFT="can_arm_l"
TRACER="can_tracer"

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

configure_openarm_can20() {
    local iface="$1"

    echo "Configuring $iface: Classic CAN 2.0, 1 Mbps"

    sudo ip link set "$iface" down
    sudo ip link set "$iface" type can fd off
    sudo ip link set "$iface" mtu 16
    sudo ip link set "$iface" type can bitrate 1000000 restart-ms 100
    sudo ip link set "$iface" up
}

configure_tracer_can20() {
    local iface="$1"

    echo "Configuring $iface: Classic CAN 2.0, 500 kbps"

    sudo ip link set "$iface" down
    sudo ip link set "$iface" type can bitrate 500000
    sudo ip link set "$iface" mtu 16
    sudo ip link set "$iface" up
}

# ---------------------------------------------------------------------------
# Validate interfaces
# ---------------------------------------------------------------------------

for iface in "$OPENARM_RIGHT" "$OPENARM_LEFT" "$TRACER"; do
    if ! ip link show "$iface" &>/dev/null; then
        echo "ERROR: CAN interface $iface not found" >&2
        exit 1
    fi
done

# ---------------------------------------------------------------------------
# Bring up interfaces
# ---------------------------------------------------------------------------

configure_openarm_can20 "$OPENARM_RIGHT"
configure_openarm_can20 "$OPENARM_LEFT"
configure_tracer_can20 "$TRACER"

# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------

for iface in "$OPENARM_RIGHT" "$OPENARM_LEFT" "$TRACER"; do
    mtu=$(cat "/sys/class/net/$iface/mtu")

    if [[ "$mtu" != "16" ]]; then
        echo "ERROR: $iface has unexpected MTU $mtu" >&2
        exit 1
    fi

    echo "===== $iface ====="
    ip -details link show "$iface"
done

echo "All CAN interfaces configured successfully."
