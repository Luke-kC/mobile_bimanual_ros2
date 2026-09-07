from pathlib import Path
from time import perf_counter

import numpy as np
import rclpy
import rclpy.time
from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import Quaternion, TransformStamped, Vector3
from rclpy.duration import Duration
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.utilities import ok as rclpy_ok
from scipy.spatial.transform import Rotation
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64MultiArray
from tf2_ros import TransformException  # type: ignore[attr-defined]
from tf2_ros.buffer import Buffer
from tf2_ros.transform_listener import TransformListener

from mobile_bimanual_teleop.core.transform_helpers import (
    map_spatial_motion,
)
from mobile_bimanual_teleop.core.yam_ik import (
    YamIK,
)
from mobile_bimanual_teleop.ros.transform_adapters import (
    transform_stamped_to_homogeneous,
)


class SingleArmTeleopNode(Node):
    def __init__(self) -> None:
        super().__init__("single_arm_teleop_node")

        yam_model_path = (
            Path(get_package_share_directory("mobile_bimanual_description"))
            / "mujoco"
            / "yam_v1"
            / "yam.xml"
        )

        self._yam_ik = YamIK(yam_model_path)
        self._print_count = 0

        self._leader_T_base_ee_ref: np.ndarray | None = None
        self._follower_T_base_ee_ref: np.ndarray | None = None

        self._tf_buffer = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self)
        self._timer = self.create_timer(0.01, self._timer_callback)

        self._follower_joint_state_sub = self.create_subscription(
            JointState,
            "/follower/joint_states",
            self._follower_joint_state_callback,
            qos_profile_sensor_data,
        )

        self._follower_command_pub = self.create_publisher(
            Float64MultiArray,
            "/follower/yam_position_controller/commands",
            10,
        )

    def _timer_callback(self) -> None:
        leader_base_frame = "world"
        leader_ee_frame = "openarm_right_hand_tcp"

        follower_base_frame = "world"
        follower_ee_frame = "gripper"

        try:
            now = rclpy.time.Time()

            leader_tf = self._tf_buffer.lookup_transform(
                target_frame=leader_base_frame,
                source_frame=leader_ee_frame,
                time=now,
                timeout=Duration(seconds=0.02),
            )

            if self._follower_T_base_ee_ref is None:
                # follower_tf = self._tf_buffer.lookup_transform(
                #     target_frame=follower_base_frame,
                #     source_frame=follower_ee_frame,
                #     time=now,
                # )
                # self._follower_T_base_ee_ref = transform_stamped_to_homogeneous(
                #     follower_tf
                # )
                self._follower_T_base_ee_ref = (
                    self._yam_ik.current_gripper_pose()
                )

        except TransformException as ex:
            self.get_logger().info(f"Could not transform: {ex}")
            return

        leader_T_base_ee = transform_stamped_to_homogeneous(leader_tf)

        if self._leader_T_base_ee_ref is None:
            self._leader_T_base_ee_ref = leader_T_base_ee

        if (
            self._leader_T_base_ee_ref is None
            or self._follower_T_base_ee_ref is None
        ):
            return

        follower_T_base_ee_desired = map_spatial_motion(
            leader_ref=self._leader_T_base_ee_ref,
            leader_cur=leader_T_base_ee,
            follower_ref=self._follower_T_base_ee_ref,
        )

        start = perf_counter()

        ik_result = self._yam_ik.solve(follower_T_base_ee_desired)

        solve_time_ms = (perf_counter() - start) * 1000.0

        if ik_result.q is None:
            self.get_logger().warning(
                "YamIK produced no follower joint commands"
            )
            return

        follower_command_ros = Float64MultiArray()
        follower_command_ros.data = ik_result.q.copy().flatten().tolist()

        self._follower_command_pub.publish(follower_command_ros)

        if self._print_count % 50 == 0:
            self.get_logger().info(
                f"IK: {solve_time_ms:.2f} ms, iterations: {ik_result.iterations}"
            )

        self._print_count += 1

        # leader_matrix_str = np.array2string(
        #     leader_spatial_delta, precision=3, suppress_small=True
        # )
        # follower_ref_str = np.array2string(
        #     self._follower_T_base_ee_ref, precision=3, suppress_small=True
        # )
        # ee_des_matrix_str = np.array2string(
        #     follower_T_base_ee_desired, precision=3, suppress_small=True
        # )
        # self.get_logger().info(
        #     f"\nLeader Spatial Transformation Matrix:\n{leader_matrix_str}"
        # )
        # self.get_logger().info(
        #     f"\nFollower Reference Transformation Matrix:\n{follower_ref_str}"
        # )
        # self.get_logger().info(
        #     f"\nFollower EE Desired Transformation Matrix:\n{ee_des_matrix_str}"
        # )

    def _follower_joint_state_callback(self, msg: JointState) -> None:
        joint_positions = np.array(msg.position)
        if len(joint_positions) == 6:
            self._yam_ik.update_current_yam_q(joint_positions)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)

    node = SingleArmTeleopNode()

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
