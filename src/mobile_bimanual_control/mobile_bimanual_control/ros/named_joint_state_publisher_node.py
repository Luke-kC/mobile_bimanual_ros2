from __future__ import annotations

import re
from typing import Any

import rclpy
from rclpy._rclpy_pybind11 import RCLError
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64


def topic_safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", name)


class NamedJointStatePublisherNode(Node):
    def __init__(self) -> None:
        super().__init__("named_joint_state_publisher")

        self.declare_parameter("input_topic", "/joint_states")
        self.declare_parameter("output_prefix", "/openarm_named_joint_states")

        self._input_topic = self.get_parameter("input_topic").value
        self._output_prefix = self.get_parameter("output_prefix").value.rstrip(
            "/"
        )
        self._field_publishers: dict[tuple[str, str], Any] = {}

        self._joint_state_sub = self.create_subscription(
            JointState,
            self._input_topic,
            self._joint_state_callback,
            qos_profile_sensor_data,
        )

        self.get_logger().info(
            f"Publishing named joint states from {self._input_topic} "
            f"under {self._output_prefix}"
        )

    def _joint_state_callback(self, msg: JointState) -> None:
        for index, joint_name in enumerate(msg.name):
            safe_name = topic_safe(joint_name)

            if index < len(msg.position):
                self._publish_value(safe_name, "position", msg.position[index])

            if index < len(msg.velocity):
                self._publish_value(safe_name, "velocity", msg.velocity[index])

            if index < len(msg.effort):
                self._publish_value(safe_name, "effort", msg.effort[index])

    def _publish_value(
        self,
        joint_name: str,
        field: str,
        value: float,
    ) -> None:
        key = (joint_name, field)

        if key not in self._field_publishers:
            topic = f"{self._output_prefix}/{joint_name}/{field}"
            self._field_publishers[key] = self.create_publisher(Float64, topic, 10)

        msg = Float64()
        msg.data = float(value)
        self._field_publishers[key].publish(msg)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = NamedJointStatePublisherNode()

    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException, RCLError):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
