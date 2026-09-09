from math import isfinite

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from sensor_msgs.msg import JointState
from rclpy.utilities import ok as rclpy_ok
from rclpy.qos import qos_profile_sensor_data
from std_msgs.msg import Float64MultiArray

from mobile_bimanual_control.core.joints import (
    LEFT_ARM_JOINTS,
    RIGHT_ARM_JOINTS,
)

COMMAND_RATE_HZ: float = 100.0


class OpenarmJointMirrorNode(Node):
    def __init__(self) -> None:
        super().__init__("openarm_joint_mirror_node")

        self._leader_positions: dict[str, float] | None = None

        self._leader_joint_state_sub = self.create_subscription(
            JointState,
            "/leader/joint_states",
            self._leader_joint_state_callback,
            qos_profile_sensor_data,
        )

        self._command_timer = self.create_timer(
            1.0 / COMMAND_RATE_HZ, self._command_timer_callback
        )

        self._sim_left_command_pub = self.create_publisher(
            Float64MultiArray,
            "/sim/left_arm_position_controller/commands",
            10,
        )

        self._sim_right_command_pub = self.create_publisher(
            Float64MultiArray,
            "/sim/right_arm_position_controller/commands",
            10,
        )

        self.get_logger().info(
            "Waiting for complete leader OpenArm joint state..."
        )

    def _leader_joint_state_callback(self, msg: JointState) -> None:
        if len(msg.position) != len(msg.name):
            self.get_logger().warning(
                "Ignoring JointState: name/position lengths differ"
            )
            return

        positions = dict(zip(msg.name, msg.position))

        required_joints = RIGHT_ARM_JOINTS + LEFT_ARM_JOINTS

        if not all(joint in positions for joint in required_joints):
            return

        if not all(isfinite(positions[joint]) for joint in required_joints):
            self.get_logger().warning(
                "Ignoring JointState, contains non-finite position(s)"
            )

        is_first_complete_state = self._leader_positions is None

        self._leader_positions = {
            joint: positions[joint] for joint in required_joints
        }

        if is_first_complete_state:
            self.get_logger().info(
                "Complete leader state received; enabling mirroring"
            )

    def _command_timer_callback(self) -> None:
        if self._leader_positions is None:
            return

        right_msg = Float64MultiArray()
        right_msg.data = [
            self._leader_positions[joint] for joint in RIGHT_ARM_JOINTS
        ]

        left_msg = Float64MultiArray()
        left_msg.data = [
            self._leader_positions[joint] for joint in LEFT_ARM_JOINTS
        ]

        self._sim_right_command_pub.publish(right_msg)
        self._sim_left_command_pub.publish(left_msg)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = OpenarmJointMirrorNode()

    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy_ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
