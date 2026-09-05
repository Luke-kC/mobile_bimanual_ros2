# Development workflow

The devcontainer is the primary build and development environment. Source code
is bind-mounted from the host, while ROS build products and editor state live in
Docker volumes.

## Prerequisites

Terminal users need:

- Docker Engine on Linux, or Docker Desktop on macOS
- The Dev Container CLI (`devcontainer`)
- Git

VS Code users need Docker and the Dev Containers extension. The standard
`.devcontainer/devcontainer.json` remains compatible with **Reopen in
Container**.

On Linux, `scripts/dev` automatically uses `.devcontainer/linux/devcontainer.json`,
which adds Docker host networking for SocketCAN hardware access. On macOS, it
uses `.devcontainer/devcontainer.json`, which keeps Docker Desktop networking
portable for editing, builds, fake hardware, and Foxglove.

## First-time terminal setup

From the repository root:

```bash
./scripts/dev up
```

This builds the image, imports pinned upstream sources, applies the project
workarounds, installs ROS dependencies, and builds the workspace. Later starts
reuse the image and the named build volumes.

Open a container shell:

```bash
./scripts/dev shell
```

Zsh shells automatically source ROS 2 Jazzy and the workspace overlay.
`scripts/dev shell` uses `TERM=xterm-256color` inside the container and forwards
`COLORTERM` when set, which keeps zsh colors and autosuggestions predictable
even when the host terminal's terminfo entry is not installed in the image.

## Neovim

When `~/.config/nvim` exists on the host, `scripts/dev` bind-mounts it into the
container. Open the workspace with:

```bash
./scripts/dev nvim
```

Only the configuration is shared with the host.

Mounts are fixed when Docker creates a container. If VS Code created the
container before `scripts/dev` added the Neovim mount, recreate it once:

```bash
./scripts/dev rebuild
```

## Zsh configuration

My personal machine has `$ZDOTDIR`, so when `$ZDOTDIR` exists on the host, `scripts/dev` bind-mounts it at
`/home/ubuntu/.config/zsh`. If `ZDOTDIR` is unset, the launcher checks
`~/.config/zsh`. Shells opened by `scripts/dev shell`, `scripts/dev nvim`, and
their equivalents use that configuration automatically.

This makes aliases, completion, autosuggestions, syntax highlighting, keybindings, and the
prompt available inside the container, if they're set up for host zsh. Zsh history and completion cache use
container-specific Docker volumes; they persist across recreation but are not
mixed with host history.

The configuration is a live host mount, so edits or plugin updates made inside
the container also affect the host configuration. Host-specific aliases that
refer to paths such as `/home/{your_user_name}` or tools outside the container remain
defined but will only work where those dependencies exist.

## Regular development

Open the editor or additional shells as needed:

```bash
./scripts/dev nvim
./scripts/dev shell
```

After changing code, package metadata, or dependencies:

```bash
./scripts/build.sh
```

Run fake hardware headlessly:

```bash
ros2 launch mobile_bimanual_bringup openarm_fake.launch.py
```

In another container shell:

```bash
ros2 control list_controllers
ros2 control list_hardware_components -v
ros2 topic echo /joint_states --once
```

Start observability and connect Foxglove to `ws://localhost:8765`:

```bash
ros2 launch mobile_bimanual_bringup observability.launch.py
```

Fake bringup does not start RViz by default, which keeps it usable in a
headless container. `launch_rviz:=true` is available in a GUI-capable native
environment.

## Linux GUI forwarding

The Linux devcontainer forwards the host X11 socket and `/dev/dri` so ROS GUI
tools and MuJoCo windows can run from inside the container. This is Linux-only;
macOS and Docker Desktop continue to use `.devcontainer/devcontainer.json`.

Before creating or rebuilding the Linux container, allow local X11 clients on
the host:

```bash
xhost +SI:localuser:$USER
```

Then recreate the container so Docker applies the GUI and GPU mounts:

```bash
./scripts/dev rebuild
```

Run GUI commands from a container shell:

```bash
./scripts/dev shell
ros2 launch mujoco_ros2_control_demos 01_basic_robot.launch.py
```

NVIDIA Docker support is selected automatically when `scripts/dev` finds a
working NVIDIA driver, `nvidia-ctk`, and a generated CDI GPU spec. After setting
up the NVIDIA Container Toolkit/CDI on a desktop or laptop, rebuild normally:

```bash
./scripts/dev rebuild
```

For troubleshooting, force the NVIDIA-specific config with:

```bash
DEVCONTAINER_NVIDIA=1 ./scripts/dev rebuild
```

Or force the standard Linux config with:

```bash
DEVCONTAINER_NVIDIA=0 ./scripts/dev rebuild
```

On hybrid laptops with an AMD integrated GPU and NVIDIA discrete GPU, the
standard Linux container uses `/dev/dri`, which is usually the integrated GPU
path. The NVIDIA-specific config also adds `--device=nvidia.com/gpu=all` and
NVIDIA runtime environment variables. If container creation fails with `failed
to discover GPU vendor from CDI`, use the standard Linux container or fix the
host NVIDIA Container Toolkit setup.

When the Dockerfile or devcontainer configuration changes:

```bash
./scripts/dev rebuild
```

## Linux hardware

SocketCAN is a Linux network interface. On Linux, `./scripts/dev up`,
`./scripts/dev shell`, `./scripts/dev nvim`, and `./scripts/dev rebuild` use a
host-networked devcontainer, so ROS nodes in the container can access host
`can0` and `can1`.

Configure and verify CAN on the host:

```bash
./scripts/can_up.sh
./scripts/can_check.sh
```

Start the container and verify that it sees the interfaces:

```bash
./scripts/dev up
./scripts/dev shell
ip -details link show can0
ip -details link show can1
```

Build and launch from inside the hardware container:

```bash
./scripts/build.sh
ros2 launch openarm_bringup openarm.bimanual.launch.py \
  arm_type:=v1.0 \
  use_fake_hardware:=false \
  right_can_interface:=can0 \
  left_can_interface:=can1 \
  robot_controller:=forward_position_controller
```

Open more terminals with `./scripts/dev shell`, or use:

```bash
./scripts/dev nvim
```


## macOS

Use `./scripts/dev up`, `./scripts/dev shell`, and `./scripts/dev nvim` for
editing, builds, tests, fake hardware, and Foxglove. Docker Desktop runs a
Linux VM and does not expose macOS hardware as Linux SocketCAN interfaces, so
direct `can0`/`can1` hardware operation is not supported.

Hardware tests from a Mac is not really supported, since I don't have a Mac. I would suggest running on a lab laptop (if we have one) or from the Jetson when we eventually set that up. 

## Native-host fallback

The existing Ubuntu 24.04 workflow is retained until real-hardware operation
has been verified in the devcontainer:

```bash
./scripts/setup_host.sh
source /opt/ros/jazzy/setup.zsh
./scripts/import_upstream.sh
./scripts/patch_openarm_can20.sh
./scripts/patch_openarm_bringup.sh
./scripts/build.sh
source install/setup.zsh
```

Build products created natively and in the devcontainer are not interchangeable.
Clean `build`, `install`, and `log` before changing between those workflows in
the same checkout.

## Container lifecycle

```bash
./scripts/dev up
./scripts/dev rebuild
./scripts/dev stop
```

`stop` stops devcontainers belonging to the current checkout. Docker volumes
remain available for the next start.
