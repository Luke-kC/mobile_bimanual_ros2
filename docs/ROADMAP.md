# Roadmap

The current development direction uses the OpenArm pair as leader arms and I2RT
YAM v1 arms as followers.

---

## M0 — Hardware baseline

- Both OpenArm CAN buses work at Classical CAN 2.0 / 1 Mbps.
- All motors are persistently in MIT mode.
- Both arms have valid stored zero positions.
- E-stop behavior is tested.

Status: **Complete**

---

## M1 — Reproducible ROS workspace

- Import OpenArm dependencies with `vcs`.
- Build with ROS 2 Jazzy.
- Commit known-good upstream dependency revisions.

Status: **Complete**

---

## M2 — Fake OpenArm ROS bringup

- Start OpenArm with fake hardware.
- Verify controller manager.
- Verify hardware interfaces.
- Verify `/joint_states`.
- Verify TF.
- Support headless bringup for container development.

Status: **Complete**

---

## M3 — Real OpenArm through ros2_control

- Bring up `can0` / `can1` in Classical CAN mode.
- Apply the temporary upstream CAN workaround when required.
- Start physical OpenArm through `ros2_control`.
- Command both arms through forward position controllers.

Status: **Complete**

---

## M3.5 — Physical gripper model

Not blocking the current leader/follower work.

- Model the lab's actual grippers.
- Reconcile stock OpenArm geometry with physical hardware.
- Document the physical gripper convention:
  - `0 rad` = closed
  - negative position = open

Status: **Deferred**

---

## M4 — OpenArm command / safety prototype

- Add the rclpy command bridge.
- Initialize commands from measured joint state.
- Add finite-value validation.
- Add OpenArm joint bounds.
- Add maximum target-step and rate limits.
- Detect stale state.
- Detect excessive tracking error.
- Safely interpolate accepted commands.

This remains useful for fake-leader motion and scripted OpenArm testing. It is
not the final physical-leader control path.

Status: **Complete**

---

## M5 — Observability and recording

- Foxglove live visualization.
- MCAP recording for current robot state and commands.
- Preserve TF and robot-description topics for debugging.

Status: **Complete**

---

## M5.5 — Initial OpenArm supervisor

- Observe controller-manager activity.
- Observe OpenArm joint-state readiness.
- Gate current command bridge with a `RobotStatus`.

The current implementation is intentionally frozen as an OpenArm command-mode
prototype. The final supervisor will be redesigned after leader/follower,
clutch, IK, and follower-safety interfaces exist.

Status: **Paused**

---

## M6 — Reproducible devcontainer

- Ubuntu 24.04 / ROS 2 Jazzy development image.
- Support x86-64 and ARM64-compatible dependencies where possible.
- Install OpenArm, ros2_control, MuJoCo ROS integration, and development tools.
- Persistent container build/install/log volumes.
- Terminal / Neovim workflow.
- VS Code Dev Containers workflow.
- Linux SocketCAN profile.
- macOS simulation/development workflow.
- Headless fake-hardware operation.

Status: **Complete**

---

# Simulation and teleoperation phase

## M7 — Single YAM v1 through ros2_control

Create:

```text
mobile_bimanual_description
mobile_bimanual_sim
```

- Vendor/pin the required I2RT YAM v1 description assets.
- Treat I2RT YAM v1 as the project source of truth for kinematics.
- Add simulation-specific actuators/interfaces as required.
- Expose six YAM joints through `ros2_control`.
- Add a YAM position controller.
- Publish simulated YAM joint state.
- Run headlessly in the devcontainer.

Status: **Complete**

---

## M8 — Simulation scene / task-environment infrastructure

Make simulation environments a first-class project feature.

- Separate robot description from task scenes.
- Add a minimal lab scene:
  - floor
  - table / bench
  - fixed fixtures
  - one movable object
- Define object naming/frame conventions.
- Add collision/contact geometry.
- Add named starting configurations / reset states.
- Add at least one simulated camera.
- Support headless simulation.
- Define how scenes are selected at launch.

Status: **Complete**

---

## M9 — Fake OpenArm leader state

- Reuse the existing fake OpenArm stack.
- Use the existing command bridge / sinusoid generator only to move fake leader
  hardware.
- Verify OpenArm joint state.
- Verify OpenArm TF.
- Identify stable leader base and end-effector frames.
- Expose the leader end-effector transform needed by teleoperation.

Status:

---

## M10 — Single-arm retargeting and YAM IK

Create:

```text
mobile_bimanual_teleop
```

Implement relative-pose mapping:

```text
leader pose at engage:   T_L0
follower pose at engage: T_F0

DeltaT_L = inverse(T_L0) * T_L(t)
T_F_des  = T_F0 * DeltaT_L
```

Status:

---

## M11 — Single-arm OpenArm -> simulated YAM teleoperation

Connect:

```text
fake OpenArm
    -> leader end-effector pose
    -> relative pose mapper
    -> YAM IK
    -> follower joint command
    -> mujoco_ros2_control
    -> simulated YAM
```

Status:

---

## M12 — Clutch and follower safety

Add explicit teleoperation state:

```text
DISENGAGED
    -> leader can be repositioned

ENGAGE
    -> capture leader/follower references

ENGAGED
    -> map relative leader motion

DISENGAGE
    -> follower holds
```

Add follower-side safety independent of the command source:

- finite-value checks;
- IK validity;
- YAM joint limits;
- maximum joint target step;
- joint-rate limits;
- leader-state timeout;
- follower-state timeout;
- follower tracking-error detection.

On unsafe or invalid input, hold/reject rather than publishing garbage.

Status:

---

## M13 — Bimanual simulated teleoperation

- Instantiate the same teleoperation pipeline for left and right arms.
- Create uniquely named left/right YAM joints.
- Place two YAM arms in a common MuJoCo scene.
- Preserve clear leader/follower and left/right ROS namespaces.
- Verify simultaneous motion.

Status:

---

## M14 — Leader/follower supervisor redesign

Redesign the supervisor around the actual system.

Potential readiness inputs:

- leader interface available;
- follower interface available;
- leader state fresh;
- follower state fresh;
- teleoperation state;
- IK health;
- follower tracking health;
- hardware faults;
- E-stop.

Potential operating states:

```text
BOOTING
INITIALIZING
READY
TELEOP
DEGRADED
FAULT
ESTOP
```

Status:

---

# Hardware

## M15 — Physical OpenArm leader mode

- Verify joint state remains available with motor torque disabled.
- Confirm physical leader motion produces correct TF/end-effector state.
- Add gravity compensation / low impedance later if needed

Status:

---

## M16 — Physical YAM follower integration

- Integrate the actual YAM hardware interface/driver.
- Preserve the same follower command contract used by simulation.
- Validate joint limits and command conventions.
- Add bimanual physical operation only after single-arm validation.

Status:

---

## M17 — Pedestal and mobile-base integration

- Define this when we get here.

Status:

---

## M18 — Cameras and VLA

- Define this when we get there.

Status:
