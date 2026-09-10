import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.utilities import ok as rclpy_ok
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64MultiArray

from mobile_bimanual_control.core.joints import (
    LEFT_ARM_JOINTS,
    RIGHT_ARM_JOINTS,
)


class OpenarmJointWatcherNode(Node):
    def __init__(self) -> None:
        super().__init__("openarm_joint_watcher_node")

        self._openarm_joint_state_sub = self.create_subscription(
            JointState,
            "/leader/joint_states",
            self._joint_state_callback,
            qos_profile_sensor_data,
        )

        self._yam_command_pub = self.create_publisher(
            Float64MultiArray,
            "/follower/yam_position_controller/commands",
            10,
        )

    def _joint_state_callback(self, msg: JointState) -> None:

        right_arm_positions: dict[str, float] = {}
        left_arm_positions: dict[str, float] = {}

        for index, joint_name in enumerate(msg.name):
            joint_position: float = msg.position[index]

            if joint_name in LEFT_ARM_JOINTS:
                left_arm_positions[joint_name] = joint_position

            if joint_name in RIGHT_ARM_JOINTS:
                right_arm_positions[joint_name] = joint_position

        left_arm_valid = all(
            joint in LEFT_ARM_JOINTS for joint in left_arm_positions
        ) and len(left_arm_positions) == len(LEFT_ARM_JOINTS)

        right_arm_valid = all(
            joint in RIGHT_ARM_JOINTS for joint in right_arm_positions
        ) and len(right_arm_positions) == len(RIGHT_ARM_JOINTS)

        if right_arm_valid:
            yam_command = Float64MultiArray()
            yam_command.data = [
                right_arm_positions[RIGHT_ARM_JOINTS[0]]
                + left_arm_positions[LEFT_ARM_JOINTS[0]],
                right_arm_positions[RIGHT_ARM_JOINTS[0]]
                - left_arm_positions[LEFT_ARM_JOINTS[0]],
                right_arm_positions[RIGHT_ARM_JOINTS[0]]
                - left_arm_positions[LEFT_ARM_JOINTS[0]],
                0,
                0,
                0,
            ]
            self._yam_command_pub.publish(yam_command)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)

    node = OpenarmJointWatcherNode()

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
