from __future__ import annotations

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import JointState
from rclpy.time import Time
from std_msgs.msg import Float64MultiArray
from trajectory_msgs.msg import JointTrajectory


import math

from mobile_bimanual_control.joint_names import (
    ARM_JOINTS,
    LEFT_ARM_JOINTS,
    RIGHT_ARM_JOINTS,
    JOINT_LIMITS,
)


class CommandBridge(Node):
    def __init__(self) -> None:
        super().__init__("command_bridge")

        self.declare_parameter("command_rate_hz", 50.0)
        self.declare_parameter("joint_state_timeout_sec", 0.1)
        self.declare_parameter("max_velocity_rad_s", 0.5)
        self.declare_parameter("max_target_step_rad", 0.25)
        self.declare_parameter("max_tracking_error_rad", 0.25)

        self._command_rate_hz = (
            self.get_parameter("command_rate_hz")
            .get_parameter_value()
            .double_value
        )

        self._joint_state_timeout_sec = (
            self.get_parameter("joint_state_timeout_sec")
            .get_parameter_value()
            .double_value
        )

        self._max_velocity_rad_s = (
            self.get_parameter("max_velocity_rad_s")
            .get_parameter_value()
            .double_value
        )

        self._max_target_step_rad = (
            self.get_parameter("max_target_step_rad")
            .get_parameter_value()
            .double_value
        )

        self._max_tracking_error_rad = (
            self.get_parameter("max_tracking_error_rad")
            .get_parameter_value()
            .double_value
        )

        self._positions: dict[str, float] = {}
        self._velocities: dict[str, float] = {}
        self._efforts: dict[str, float] = {}

        self._command_positions: dict[str, float] = {}

        self._target_positions: dict[str, float] = {}
        self._last_target_time: Time | None = None

        self._have_complete_state: bool = False
        self._command_initialized: bool = False

        self._last_joint_state_time: Time | None = None

        self._state_stale: bool = False
        self._tracking_fault: bool = False

        self.get_logger().info("Waiting for complete arm joint state...")

        self._joint_state_sub = self.create_subscription(
            JointState,
            "/joint_states",
            self._joint_state_callback,
            qos_profile_sensor_data,
        )

        self._joint_target_sub = self.create_subscription(
            JointTrajectory,
            "/mobile_bimanual/joint_targets",
            self._joint_target_callback,
            10,
        )

        self._right_command_pub = self.create_publisher(
            Float64MultiArray,
            "right_forward_position_controller/commands",
            10,
        )

        self._left_command_pub = self.create_publisher(
            Float64MultiArray,
            "left_forward_position_controller/commands",
            10,
        )

        self._command_timer = self.create_timer(
            1.0 / self._command_rate_hz,
            self._command_timer_callback,
        )

    def _joint_state_callback(self, msg: JointState) -> None:

        if len(msg.name) != len(msg.position):
            self.get_logger().warning(
                "Ignoring JointState: name and position lengths do not match"
            )
            return

        for index, name in enumerate(msg.name):
            self._positions[name] = msg.position[index]

            if index < len(msg.velocity):
                self._velocities[name] = msg.velocity[index]

            if index < len(msg.effort):
                self._efforts[name] = msg.effort[index]

        self._last_joint_state_time = self.get_clock().now()

        if not self._have_complete_state and self._has_complete_arm_state():
            self._have_complete_state = True
            self._report_initial_state()
            self._initialize_command_state()

    def _has_complete_arm_state(self) -> bool:
        return all(joint in self._positions for joint in ARM_JOINTS)

    def _report_initial_state(self) -> None:
        right_positions: list[float] = [
            self._positions[joint] for joint in RIGHT_ARM_JOINTS
        ]

        left_positions: list[float] = [
            self._positions[joint] for joint in LEFT_ARM_JOINTS
        ]

        self.get_logger().info("Complete bimanual arm state received")

        self.get_logger().info(
            f"Right arm: {self._format_positions(right_positions)}"
        )
        self.get_logger().info(
            f"Left arm: {self._format_positions(left_positions)}"
        )

        self.get_logger().info("Command bridge state cache ready")

    def _joint_state_is_fresh(self) -> bool:
        if self._last_joint_state_time is None:
            return False

        age: float = (
            self.get_clock().now() - self._last_joint_state_time
        ).nanoseconds / 1e9

        return age < self._joint_state_timeout_sec

    def _initialize_command_state(self) -> None:
        self._command_positions = {
            joint: self._positions[joint] for joint in ARM_JOINTS
        }

        self._target_positions = dict(self._command_positions)

        self._command_initialized = True

        right_commands = [
            self._command_positions[joint] for joint in RIGHT_ARM_JOINTS
        ]

        left_commands = [
            self._command_positions[joint] for joint in LEFT_ARM_JOINTS
        ]

        self.get_logger().info(
            "Command state initialized from measured joint state"
        )
        self.get_logger().info(
            f"Initial right command: {self._format_positions(right_commands)}"
        )
        self.get_logger().info(
            f"Initial left command:  {self._format_positions(left_commands)}"
        )

    def _make_arm_command(
        self,
        joint_names: list[str],
    ) -> Float64MultiArray:
        msg = Float64MultiArray()

        msg.data = [self._command_positions[joint] for joint in joint_names]

        return msg

    def _publish_arm_commands(self) -> None:
        if not self._command_initialized:
            return

        right_msg: Float64MultiArray = self._make_arm_command(RIGHT_ARM_JOINTS)
        left_msg: Float64MultiArray = self._make_arm_command(LEFT_ARM_JOINTS)

        self._right_command_pub.publish(right_msg)
        self._left_command_pub.publish(left_msg)

    def _command_timer_callback(self) -> None:
        if not self._command_initialized:
            return

        if not self._joint_state_is_fresh():
            if not self._state_stale:
                self.get_logger().error(
                    "Joint state is stale; suspending command updates"
                )
                self._state_stale = True
            return

        if self._state_stale:
            self.get_logger().info(
                "Joint state recovered; resuming command updates"
            )
            self._state_stale = False

        if not self._tracking_error_is_safe():
            return

        self._update_command_positions()
        self._publish_arm_commands()

    def _joint_target_callback(self, msg: JointTrajectory) -> None:
        if not self._command_initialized:
            self.get_logger().warning(
                "Rejecting target: command state is not initialized"
            )
            return

        if not self._joint_state_is_fresh():
            self.get_logger().warning("Rejecting target: joint state is stale")
            return

        if self._tracking_fault:
            self.get_logger().warning(
                "Rejecting target: tracking fault is active"
            )
            return

        if len(msg.points) != 1:
            self.get_logger().warning(
                "Rejecting target: expected exactly one trajectory point"
            )
            return

        if not msg.joint_names:
            self.get_logger().warning("Rejecting target: no joints specified")
            return

        positions: list[float] = msg.points[0].positions

        if len(msg.joint_names) != len(positions):
            self.get_logger().warning(
                "Rejecting target: joint_names and positions lengths are different"
            )
            return

        if len(set(msg.joint_names)) != len(msg.joint_names):
            self.get_logger().warning("Rejecting target: duplicate joint names")
            return

        for joint, position in zip(msg.joint_names, positions):
            if joint not in ARM_JOINTS:
                self.get_logger().warning(
                    f"Rejecting target: unknown/unsupported joint '{joint}'"
                )
                return

            if not math.isfinite(position):
                self.get_logger().warning(
                    f"Rejecting target: non-finite position for '{joint}'"
                )
                return

            lower, upper = JOINT_LIMITS[joint]

            if position < lower or position > upper:
                self.get_logger().warning(
                    f"Rejecting target: '{joint}' position "
                    f"{position:+.4f} rad is outside "
                    f"[{lower:+.4f}, {upper:+.4f}]"
                )
                return

            command = self._command_positions[joint]
            target_step = abs(position - command)

            if target_step > self._max_target_step_rad:
                self.get_logger().warning(
                    f"Rejecting target: '{joint}' step "
                    f"{target_step:.4f} rad exceeds "
                    f"{self._max_target_step_rad:.4f} rad"
                )
                return

        for joint, position in zip(msg.joint_names, positions):
            self._target_positions[joint] = position

        self._last_target_time = self.get_clock().now()

        targets = ", ".join(
            f"{joint}={position:+.4f}"
            for joint, position in zip(
                msg.joint_names,
                positions,
            )
        )

        self.get_logger().info(f"Accepted target: {targets}")

    def _update_command_positions(self) -> None:
        max_step = self._max_velocity_rad_s / self._command_rate_hz

        for joint in ARM_JOINTS:
            command = self._command_positions[joint]
            target = self._target_positions[joint]

            error = target - command

            if abs(error) <= max_step:
                self._command_positions[joint] = target
            elif error > 0.0:
                self._command_positions[joint] = command + max_step
            else:
                self._command_positions[joint] = command - max_step

    def _tracking_error_is_safe(self) -> bool:
        for joint in ARM_JOINTS:
            error = abs(self._command_positions[joint] - self._positions[joint])

            if error > self._max_tracking_error_rad:
                if not self._tracking_fault:
                    self.get_logger().error(
                        f"Tracking error too large for '{joint}': "
                        f"{error:.4f} rad; suspending command updates"
                    )
                    self._tracking_fault = True

                return False

        if self._tracking_fault:
            self.get_logger().info(
                "Tracking error recovered; resuming command updates"
            )
            self._tracking_fault = False

        return True

    @staticmethod
    def _format_positions(positions: list[float]) -> str:
        values = ", ".join(f"{position:+.4f}" for position in positions)
        return f"[{values}]"


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)

    node = CommandBridge()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
