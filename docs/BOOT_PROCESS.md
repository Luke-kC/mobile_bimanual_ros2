# Boot process


## Current process

1. Launch with openarm bringup

```zsh
ros2 launch openarm_bringup openarm.bimanual.launch.py \
arm_type:=v1.0 \
use_fake_hardware:=false \
right_can_interface:=can0 \
left_can_interface:=can1 \
robot_controller:=forward_position_controller
```

2. Run publisher that remaps openarm joint indices to actual named fields
```zsh
ros2 run mobile_bimanual_control named_joint_state_publisher
```

3. Launch local foxglove server for live data
```zsh
ros2 launch mobile_bimanual_bringup observability.launch.py
```

4. Launch lab-side high level controller
```zsh
ros2 launch mobile_bimanual_bringup control.launch.py
```

5. Run a trajectory generator (optional)
```zsh
ros2 run mobile_bimanual_control sinusoid_position_request
```

These nodes and which package they belong can be changed, the current ones are just prototypes.

## Proposed process

```mermaid
flowchart TD
    START["ros2 launch mobile_bimanual_bringup robot.launch.py"]

    START --> RSP["robot_state_publisher"]
    START --> CM["ros2_control controller_manager"]
    START --> SUP["robot_supervisor_node"]
    START --> BRIDGE["command_bridge_node"]
    START --> OBS["Foxglove / observability"]

    CM --> HW["OpenArmHW<br/>left + right"]

    HW --> INIT["OpenArmHW::on_activate()"]
    INIT --> ENABLE["Enable motors"]
    ENABLE --> ZERO["return_to_zero()<br/>~2 s interpolation to 0 rad"]
    ZERO --> ACTIVE["Hardware ACTIVE"]

    CM --> JSB["joint_state_broadcaster"]
    CM --> FPC["left/right forward_position_controller"]

    JSB --> JS["/joint_states"]

    CM --> ACTIVITY["/controller_manager/activity"]
    ACTIVITY --> SUP
    JS --> SUP

    SUP --> STATE{"Supervisor state"}

    STATE -->|"hardware not active"| INITIALIZING["INITIALIZING"]
    STATE -->|"controllers not active"| INITIALIZING
    STATE -->|"joint state missing"| INITIALIZING

    STATE -->|"all required components ready"| READY["READY"]
    STATE -->|"runtime dependency lost"| DEGRADED["DEGRADED / NOT READY"]
    STATE -->|"serious fault"| FAULT["FAULT"]

    READY --> STATUS["/mobile_bimanual/status<br/>external_commands_allowed = true"]

    INITIALIZING --> STATUS2["external_commands_allowed = false"]
    DEGRADED --> STATUS2
    FAULT --> STATUS2

    STATUS --> BRIDGE
    STATUS2 --> BRIDGE

    TELEOP["Teleop"]
    SCRIPT["Scripted tests"]
    VLA["Future VLA / planner"]

    TELEOP --> REQUEST["/mobile_bimanual/joint_targets"]
    SCRIPT --> REQUEST
    VLA --> REQUEST
    REQUEST --> BRIDGE

    JS --> BRIDGE

    BRIDGE --> LOCAL{"Local command safety"}

    LOCAL -->|"supervisor not READY"| HOLD["Suspend / hold"]
    LOCAL -->|"state stale"| HOLD
    LOCAL -->|"tracking fault"| HOLD
    LOCAL -->|"invalid target"| REJECT["Reject"]
    LOCAL -->|"safe"| COMMAND["Safe interpolated command"]

    COMMAND --> FPC
    FPC --> HW

    BRIDGE --> CMDSTATUS["/mobile_bimanual/command_status"]
    STATUS --> OBS
    CMDSTATUS --> OBS
    JS --> OBS
```


