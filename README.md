# mobile_bimanual_ros2

ROS 2 Jazzy workspace for a mobile bimanual manipulation platform built from an AgileX Tracer base, a telescoping pedestal, and two OpenArm v1.0 arms.

## Requirements

- **Linux host:** Ubuntu 24.04 (the development target), Docker Engine, and the [Dev Container CLI](https://github.com/devcontainers/cli). The host needs working USB/CAN drivers. ROS 2 runs inside the development container for the main workspace.
- **Hardware:** USB connections for the dual-channel OpenArm CAN adapter, Tracer CAN adapter, and pedestal ESP32 as needed.
- **Development:** Git; a terminal or editor with Dev Containers support. See [development notes](docs/DEVELOPMENT.md) for container, editor, GPU, and GUI details.

## First-time setup on a new Linux computer

### 1. Clone the repository

```bash
# On the host
git clone git@github.com:Luke-kC/mobile_bimanual_ros2.git
cd mobile_bimanual_ros2
```

Install Docker Engine and the Dev Container CLI if they are not already available. Ensure your user can use Docker. This repository's `scripts/dev` helper requires both `docker` and `devcontainer` on the host.

### 2. Install persistent CAN interface names (host; once per computer)

Connect the CAN adapters, then install the checked-in udev rules and `systemd.link` files:

```bash
# On the host, from the repository root
./scripts/install_can_rules.sh
sudo reboot
```

After reboot, verify that the interfaces match their **physical** hardware channels:

```bash
ip -brief link show type can
```

| Interface | Assigned hardware | Bus configuration |
| --- | --- | --- |
| `can_arm_r` | PEAK adapter channel 0 → right OpenArm | Classic CAN 2.0, 1 Mbps |
| `can_arm_l` | PEAK adapter channel 1 → left OpenArm | Classic CAN 2.0, 1 Mbps |
| `can_tracer` | candleLight adapter → Tracer | Classic CAN 2.0, 500 kbps |

Rules are in [`config/can/`](config/can/). They were written for the current PEAK and candleLight adapters; **recheck adapter IDs and channel-to-arm wiring on a replacement computer or after changing adapters**. The two PEAK channels are identified by channel ID, while the candleLight rule matches its USB serial.

The rules provide stable names, but they **do not activate the CAN interfaces**.

### 3. Bring up CAN (host; each time after boot)

```bash
# On the host; before starting ROS hardware drivers
./scripts/can_up.sh
ip -details link show can_arm_r
ip -details link show can_arm_l
ip -details link show can_tracer
```

`can_up.sh` configures the OpenArm buses with CAN FD disabled, MTU 16, and 1 Mbps. It configures the Tracer interface for 500 kbps. All three should be `UP` with MTU 16. Do **not** run the script while hardware controllers are active: it takes the interfaces down during reconfiguration.

See [`docs/CAN20_OPENARM_ROS2.md`](docs/CAN20_OPENARM_ROS2.md) for the OpenArm CAN 2.0 workaround.

### 4. Create the development container

Connect the pedestal ESP32 **before** creating the container if you intend to run the pedestal. The development helper maps the recognized USB serial device into the container as `/dev/pedestal`.

```bash
# On the host
./scripts/dev up
./scripts/dev shell
```

On initial creation, `.devcontainer/post-create.sh` imports the pinned upstream repositories, applies the OpenArm launch/CAN workarounds, installs dependencies, and builds the supported workspace packages.

If the automatic build did not complete, run **inside the container**:

```bash
./scripts/build.sh
source /opt/ros/jazzy/setup.zsh
source /workspace/install/setup.zsh
```

If you attach the pedestal ESP32 after the container was created, recreate it **on the host** to apply device passthrough:

```bash
./scripts/dev rebuild
./scripts/dev shell
ls -l /dev/pedestal
```

The helper currently expects `/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0` on the host. If a different ESP32/USB-serial adapter is used, update that mapping in `scripts/dev` first. `DEVCONTAINER_PEDESTAL=1 ./scripts/dev rebuild` requires the device to be present and fails if it is missing.

### 5. Bring up the OpenArms and pedestal (container)

Power the equipment, ensure the Tracer cannot move, and confirm the CAN interfaces are up on the host. From **inside** `./scripts/dev shell`:

```bash
source /opt/ros/jazzy/setup.zsh
source /workspace/install/setup.zsh

ros2 launch mobile_bimanual_bringup pedestal_openarm.launch.py \
  use_fake_hardware:=false
```

This launch starts the OpenArm control stack, pedestal serial node, the combined pedestal/OpenArm robot description and joint-state relays, RViz, and a Foxglove bridge. It does **not** start the Tracer driver or publish a whole-robot Tracer-to-pedestal transform.

Check the running system from another container shell:

```bash
ros2 control list_controllers -c /leader/controller_manager
ros2 topic echo /pedestal/joint_states --once
ros2 topic echo /pedestal/position_valid --once
ros2 topic echo /joint_states --once
```

The pedestal stop service is:

```bash
ros2 service call /pedestal/stop std_srvs/srv/Trigger '{}'
```

## Normal startup (after initial setup)

**On the host:**

```bash
cd mobile_bimanual_ros2
./scripts/can_up.sh
./scripts/dev up
./scripts/dev shell
```

**If the container is not starting/tossing errors, try stopping and restarting:**
```bash
./scripts/dev stop
./scripts/dev up
```

**Inside the container:**

```bash
source /opt/ros/jazzy/setup.zsh
source /workspace/install/setup.zsh
ros2 launch mobile_bimanual_bringup pedestal_openarm.launch.py \
  use_fake_hardware:=false
```

Use `./scripts/dev shell` on the host to open additional container terminals. Launch the separately installed Tracer driver from its own workspace only when needed.

Use `./scripts/tmux-ros.sh` in the container to split terminal into a 2x2 grid.

## Development without hardware

You can start the container and use fake OpenArm hardware without connecting CAN devices:

```bash
./scripts/dev up
./scripts/dev shell
source /opt/ros/jazzy/setup.zsh
source /workspace/install/setup.zsh
ros2 launch mobile_bimanual_bringup openarm_fake.launch.py
```

For terminal/Neovim development use `./scripts/dev nvim`. VS Code users can open the repository and choose **Dev Containers: Reopen in Container**. Details: [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md).

## Visualization and recording

The OpenArm/pedestal combined launch already starts a Foxglove bridge. Connect Foxglove to:

```text
ws://localhost:8765
```

To start the bridge independently (when another launch has not already started it):

```bash
ros2 launch mobile_bimanual_bringup observability.launch.py
```

Record an MCAP with the existing helper:

```bash
./scripts/record_mcap.sh
```

## Repository layout

```text
config/can/                       Persistent CAN device names
scripts/                          Host setup, container, build and recording helpers
firmware/pedestal_controller/      ESP32 pedestal control firmware
src/mobile_bimanual_bringup/       ROS launch/configuration
src/mobile_bimanual_description/   Pedestal and OpenArm URDF/Xacro
src/mobile_bimanual_hardware/      Pedestal ROS/serial driver
src/mobile_bimanual_control/       OpenArm command/control utilities
src/mobile_bimanual_interfaces/    Project ROS interfaces
tools/foxglove/                   Custom Foxglove tools
docs/                             Engineering and development notes
upstream.repos.lock               Pinned upstream dependencies
```

Other experimental packages may remain in the source tree; the setup above describes the current physical-robot workflow.

## Additional documentation

- [Development environment](docs/DEVELOPMENT.md)
- [OpenArm Classic CAN 2.0 notes](docs/CAN20_OPENARM_ROS2.md)
- [Visualization and MCAP recording](docs/DATA_VISUALIZATION_AND_RECORDING.md)
- [Code guidelines](docs/CODE_GUIDELINES.md)
