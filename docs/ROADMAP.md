# Roadmap

## M0 — Hardware baseline

- Both CAN buses work at classic CAN 2.0 / 1 Mbps.
- All motors are persistently in MIT mode.
- Both arms have valid stored zero positions.
- E-stop behavior is tested.

Status: Complete

## M1 — Reproducible ROS workspace

- Import OpenArm dependencies with `vcs`.
- Build with ROS 2 Jazzy.
- Commit a dependency lock after the first known-good build.

Status: Complete

## M2 — Fake-hardware ROS bringup

- Start OpenArm with mock hardware.
- Verify controller manager, hardware interfaces, `/joint_states`, and TF.

Status: Complete

## M3 — Real OpenArm through ros2_control

- Bring up can0/can1 in classic CAN mode.
- Apply the temporary CAN 2.0 OpenArm Xacro workaround if still needed upstream.
- Start real OpenArm hardware with `forward_position_controller`.

Status: Complete

## M3.5 (Not blocking) — Robot Model

- Model the lab's custom grippers in `mobile_bimanual_description`
- Stock OpenArm vs gripper URDF does not match physical hardware
- Both physical grippers currently use 0 rad = closed and negative position = open

Status:

## M4 — Python command layer

- Add an rclpy command bridge.
- Read current joint state before accepting commands.
- Add timeout, finite-value checks, joint bounds, max-step/rate bounds, and safe interpolation.

Status: Complete

## M5 — Observability and recording

- Foxglove live visualization.
- MCAP recording for commands, states, TF, and later cameras/base/pedestal.

Status: Complete

## M6 — Whole-robot description

- Create the lab-owned URDF/Xacro root.
- Mount OpenArm torso on a pedestal link.
- Mount pedestal on the mobile base.
- One TF tree represents base -> pedestal -> torso -> arms.

Status:

## M7 — Pedestal integration

- Add a vendor driver or ros2_control hardware component for the telescoping joint.

Status:

## M8 — Mobile-base integration

- Add the base driver; expose odometry and velocity commands.

Status:

## M9 — Whole-body command bridge

- Define a hardware-independent command contract.
- Route arm targets, grippers, pedestal, and base through a single safety boundary.
- Teleop/scripted/VLA sources can be swapped without changing hardware drivers.

Status:

## M10 — Learning data contract

- Define observation/action ordering and units.
- Record RGB, robot state, commands, timestamps, and task metadata.

Status:

## M11 — VLA inference

- VLA publishes policy actions only to the command bridge.
- Safety and actuator layers remain independent of the model.

Status:
