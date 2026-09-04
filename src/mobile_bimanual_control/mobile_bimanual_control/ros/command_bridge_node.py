from __future__ import annotations

from mobile_bimanual_interfaces.msg import RobotStatus
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64MultiArray
from trajectory_msgs.msg import JointTrajectory

from mobile_bimanual_control.core.controller import (
    BimanualController,
)

from mobile_bimanual_control.core.joints import (
    LEFT_ARM_JOINTS,
    RIGHT_ARM_JOINTS,
)

from mobile_bimanual_control.core.models import (
    ControllerConfig,
    JointStateSnapshot,
    JointTarget,
)


class CommandBridgeNode(Node):
    def __init__(self) -> None:
        super().__init__("command_bridge_node")

        self._external_command_allowed = False

        self._controller: BimanualController = BimanualController(
            self._load_config()
        )

        self.get_logger().info("Waiting for complete arm joint state...")

        self._supervisor_sub = self.create_subscription(
            RobotStatus,
            "mobile_bimanual/supervisor/robot_status",
            self._supervisor_callback,
            10,
        )

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
            1.0 / self._config.command_rate_hz,
            self._command_timer_callback,
        )

    def _load_config(self) -> ControllerConfig:
        self.declare_parameter(
            "command_rate_hz",
            50.0,
        )
        self.declare_parameter(
            "joint_state_timeout_sec",
            0.1,
        )
        self.declare_parameter(
            "max_velocity_rad_s",
            0.5,
        )
        self.declare_parameter(
            "max_target_step_rad",
            0.25,
        )
        self.declare_parameter(
            "max_tracking_error_rad",
            0.25,
        )

        self._config = ControllerConfig(
            command_rate_hz=self.get_parameter("command_rate_hz").value,
            joint_state_timeout_sec=self.get_parameter(
                "joint_state_timeout_sec"
            ).value,
            max_velocity_rad_s=self.get_parameter("max_velocity_rad_s").value,
            max_target_step_rad=self.get_parameter("max_target_step_rad").value,
            max_tracking_error_rad=self.get_parameter(
                "max_tracking_error_rad"
            ).value,
        )

        return self._config

    def _supervisor_callback(self, msg: RobotStatus) -> None:
        self._external_command_allowed = msg.external_commands_allowed

    def _joint_state_callback(
        self,
        msg: JointState,
    ) -> None:
        if len(msg.name) != len(msg.position):
            self.get_logger().warning(
                "Ignoring JointState: name and position lengths do not match"
            )
            return

        positions = dict(zip(msg.name, msg.position))

        velocities = {
            name: msg.velocity[index]
            for index, name in enumerate(msg.name)
            if index < len(msg.velocity)
        }

        efforts = {
            name: msg.effort[index]
            for index, name in enumerate(msg.name)
            if index < len(msg.effort)
        }

        snapshot = JointStateSnapshot(
            positions=positions,
            velocities=velocities,
            efforts=efforts,
            received_time_sec=self._now_sec(),
        )

        initialized_now = self._controller.update_state(snapshot)

        if initialized_now:
            self._report_initial_state()

    def _joint_target_callback(
        self,
        msg: JointTrajectory,
    ) -> None:
        if len(msg.points) != 1:
            self._reject_target("expected exactly one trajectory point")
            return

        if not msg.joint_names:
            self._reject_target("no joints specified")
            return

        positions = msg.points[0].positions

        if len(msg.joint_names) != len(positions):
            self._reject_target(
                "joint_names and positions lengths are different"
            )
            return

        if len(set(msg.joint_names)) != len(msg.joint_names):
            self._reject_target("duplicate joint names")
            return

        target = JointTarget(
            positions=dict(
                zip(
                    msg.joint_names,
                    positions,
                )
            )
        )

        result = self._controller.set_target(
            target=target,
            now_sec=self._now_sec(),
        )

        if not result.accepted:
            self._reject_target(result.reason or "unknown reason")
            return

        # targets = ", ".join(
        #     f"{joint}={position:+.4f}"
        #     for joint, position in target.positions.items()
        # )

        # self.get_logger().info(f"Accepted target: {targets}")

    def _command_timer_callback(self) -> None:

        if not self._external_command_allowed:
            return

        result = self._controller.step(self._now_sec())

        if result.state_became_stale:
            self.get_logger().error(
                "Joint state is stale; suspending command updates"
            )

        if result.state_recovered:
            self.get_logger().info(
                "Joint state recovered; resuming command updates"
            )

        if result.tracking_fault_activated:
            self.get_logger().error(
                "Tracking error too large for"
                f"'{result.fault_joint}': "
                f"{result.tracking_error_rad:.4f} rad; suspending command updates"
            )

        if result.tracking_fault_recovered:
            self.get_logger().info(
                "Tracking error recovered; resuming command updates"
            )

        if result.command_positions is None:
            return

        self._publish_arm_commands(result.command_positions)

    def _publish_arm_commands(
        self, command_positions: dict[str, float]
    ) -> None:
        right_msg = self._make_arm_command(
            command_positions,
            RIGHT_ARM_JOINTS,
        )

        left_msg = self._make_arm_command(
            command_positions,
            LEFT_ARM_JOINTS,
        )

        self._right_command_pub.publish(right_msg)

        self._left_command_pub.publish(left_msg)

    @staticmethod
    def _make_arm_command(
        command_positions: dict[str, float],
        joint_names: list[str],
    ) -> Float64MultiArray:

        msg = Float64MultiArray()

        msg.data = [command_positions[joint] for joint in joint_names]

        return msg

    def _report_initial_state(self) -> None:
        measured = self._controller.measured_positions

        commanded = self._controller.command_positions

        right_measured = [measured[joint] for joint in RIGHT_ARM_JOINTS]

        left_measured = [measured[joint] for joint in LEFT_ARM_JOINTS]

        right_commanded = [commanded[joint] for joint in RIGHT_ARM_JOINTS]

        left_commanded = [commanded[joint] for joint in LEFT_ARM_JOINTS]

        self.get_logger().info("Complete bimanual arm state received")

        self.get_logger().info(
            f"Right arm: {self._format_positions(right_measured)}"
        )

        self.get_logger().info(
            f"Left arm:  {self._format_positions(left_measured)}"
        )

        self.get_logger().info(
            "Command state initialized from measured joint state"
        )

        self.get_logger().info(
            f"Initial right command: {self._format_positions(right_commanded)}"
        )

        self.get_logger().info(
            f"Initial left command:  {self._format_positions(left_commanded)}"
        )

    def _reject_target(
        self,
        reason: str,
    ) -> None:
        self.get_logger().warning(f"Rejecting target: {reason}")

    def _now_sec(self) -> float:
        return self.get_clock().now().nanoseconds / 1e9

    @staticmethod
    def _format_positions(
        positions: list[float],
    ) -> str:
        values = ", ".join(f"{position:+.4f}" for position in positions)

        return f"[{values}]"


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)

    node = CommandBridgeNode()

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
