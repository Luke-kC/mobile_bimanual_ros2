import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.time import Time
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from builtin_interfaces.msg import Duration

from mobile_bimanual_control.core.joints import (
    RIGHT_ARM_JOINTS,
    LEFT_ARM_JOINTS,
    ARM_JOINTS,
    JOINT_LIMITS,
    ALL_JOINTS,
)


TRAJECTORY_GENERATOR_HZ = 50
FUNCTION_FREQ_HZ: float = 0.05


class SinusoidPositionRequestNode(Node):
    def __init__(self) -> None:
        super().__init__("sinusoid_position_request_node")

        self._initialize_time: Time = self.get_clock().now()

        self._trajectory_timer = self.create_timer(
            1.0 / TRAJECTORY_GENERATOR_HZ,
            self._trajectory_timer_callback,
        )

        self._target_pub = self.create_publisher(
            JointTrajectory, "mobile_bimanual/joint_targets", 10
        )

    def _trajectory_timer_callback(self) -> None:

        now = self.get_clock().now()
        time_s: float = (now - self._initialize_time).nanoseconds / 1e9

        sine_val = 0.35 * np.sin(2.0 * np.pi * FUNCTION_FREQ_HZ * time_s)

        msg: JointTrajectory = JointTrajectory()
        msg.header.stamp = now.to_msg()
        point = JointTrajectoryPoint()

        for joint in ARM_JOINTS:
            lower, upper = JOINT_LIMITS[joint]

            if sine_val < 0.0:
                target_rad = (
                    -sine_val * lower if lower > 0 else abs(sine_val) * lower
                )
            else:
                target_rad = sine_val * upper

            target_rad = np.clip(target_rad, lower, upper)

            if joint == ARM_JOINTS[1]:
                target_rad = np.clip(target_rad, 0.0, 3.3161)

            if joint == ARM_JOINTS[8]:
                target_rad = np.clip(target_rad, -3.3161, 0.0)

            if joint in RIGHT_ARM_JOINTS:
                if sine_val >= 0.0:
                    msg.joint_names.append(joint)
                    point.positions.append(target_rad)

            if joint in LEFT_ARM_JOINTS:
                if sine_val <= 0.0:
                    msg.joint_names.append(joint)
                    point.positions.append(target_rad)

        point.time_from_start = Duration(
            sec=0, nanosec=int(1e9 / TRAJECTORY_GENERATOR_HZ)
        )

        msg.points.append(point)

        self._target_pub.publish(msg)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)

    node = SinusoidPositionRequestNode()

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
