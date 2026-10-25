from __future__ import annotations

import math
import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, qos_profile_sensor_data
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64, Float64MultiArray, String
from std_srvs.srv import Trigger

from mobile_bimanual_control.core.operating_modes import (
    OperatingMode,
    OperatingModeController,
    Subsystem,
)
from mobile_bimanual_interfaces.srv import SetOperatingMode

LEFT_JOINTS = tuple(f"openarm_left_joint{i}" for i in range(1, 8))
RIGHT_JOINTS = tuple(f"openarm_right_joint{i}" for i in range(1, 8))


class CommandGateNode(Node):
    def __init__(self) -> None:
        super().__init__("command_gate_node")
        self.declare_parameter("joint_feedback_timeout_s", 0.5)
        self._joint_timeout = float(
            self.get_parameter("joint_feedback_timeout_s").value
        )
        if not math.isfinite(self._joint_timeout) or self._joint_timeout <= 0:
            raise ValueError(
                "joint_feedback_timeout_s must be finite and positive"
            )

        self._controller = OperatingModeController()
        self._transitioning = False
        self._joint_positions: dict[str, float] = {}
        self._joint_stamp: float | None = None
        self._had_pedestal_command = False
        self._had_base_command = False
        self._mode_pub = self.create_publisher(
            String,
            "/mobile_bimanual/operating_mode",
            QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL),
        )
        # Public topics keep existing teleop and Foxglove interfaces unchanged.
        # The /hardware outputs go ONLY to launch-remapped hardware subscribers.
        self._base_pub = self.create_publisher(Twist, "/hardware/cmd_vel", 10)
        self._pedestal_pub = self.create_publisher(
            Float64, "/hardware/pedestal/position_target", 10
        )
        self._left_pub = self.create_publisher(
            Float64MultiArray,
            "/hardware/leader/left_forward_position_controller/commands",
            10,
        )
        self._right_pub = self.create_publisher(
            Float64MultiArray,
            "/hardware/leader/right_forward_position_controller/commands",
            10,
        )
        self._stop_client = self.create_client(Trigger, "/pedestal/stop")
        self._service_group = MutuallyExclusiveCallbackGroup()
        self._mode_srv = self.create_service(
            SetOperatingMode,
            "/mobile_bimanual/set_operating_mode",
            self._set_mode,
            callback_group=self._service_group,
        )
        self._subscriptions = [
            self.create_subscription(Twist, "/cmd_vel", self._on_base, 10),
            self.create_subscription(
                Float64, "/pedestal/position_target", self._on_pedestal, 10
            ),
            self.create_subscription(
                Float64MultiArray,
                "/leader/left_forward_position_controller/commands",
                self._on_left,
                10,
            ),
            self.create_subscription(
                Float64MultiArray,
                "/leader/right_forward_position_controller/commands",
                self._on_right,
                10,
            ),
            self.create_subscription(
                JointState,
                "/leader/joint_states",
                self._on_joints,
                qos_profile_sensor_data,
            ),
        ]
        self._mode_timer = self.create_timer(0.1, self._publish_mode)
        self._publish_mode()
        self.get_logger().info(
            "Gate starts in NO_MOTION; public command topics active"
        )

    def _allowed(self, subsystem: Subsystem) -> bool:
        return not self._transitioning and self._controller.is_command_allowed(
            subsystem
        )

    def _on_base(self, msg: Twist) -> None:
        if not self._allowed(Subsystem.TRACER):
            return
        values = (
            msg.linear.x,
            msg.linear.y,
            msg.linear.z,
            msg.angular.x,
            msg.angular.y,
            msg.angular.z,
        )
        if all(math.isfinite(v) for v in values):
            self._base_pub.publish(msg)
            self._had_base_command = True

    def _on_pedestal(self, msg: Float64) -> None:
        if self._allowed(Subsystem.PEDESTAL) and math.isfinite(msg.data):
            self._pedestal_pub.publish(msg)
            self._had_pedestal_command = True

    def _on_left(self, msg: Float64MultiArray) -> None:
        if (
            self._allowed(Subsystem.OPENARM)
            and len(msg.data) == 7
            and all(math.isfinite(v) for v in msg.data)
        ):
            self._left_pub.publish(msg)

    def _on_right(self, msg: Float64MultiArray) -> None:
        if (
            self._allowed(Subsystem.OPENARM)
            and len(msg.data) == 7
            and all(math.isfinite(v) for v in msg.data)
        ):
            self._right_pub.publish(msg)

    def _on_joints(self, msg: JointState) -> None:
        if len(msg.name) != len(msg.position):
            return
        self._joint_positions = {
            name: float(position)
            for name, position in zip(msg.name, msg.position)
            if math.isfinite(position)
        }
        self._joint_stamp = time.monotonic()

    def _hold_arms(self) -> tuple[bool, str]:
        if (
            self._joint_stamp is None
            or time.monotonic() - self._joint_stamp > self._joint_timeout
        ):
            return (
                False,
                "OpenArm joint feedback missing or stale; hold not sent",
            )
        if any(
            j not in self._joint_positions for j in LEFT_JOINTS + RIGHT_JOINTS
        ):
            return False, "OpenArm joint feedback incomplete; hold not sent"
        self._left_pub.publish(
            Float64MultiArray(
                data=[self._joint_positions[j] for j in LEFT_JOINTS]
            )
        )
        self._right_pub.publish(
            Float64MultiArray(
                data=[self._joint_positions[j] for j in RIGHT_JOINTS]
            )
        )
        return True, "OpenArm hold targets published (not motion-confirmed)"

    async def _stop_previous(self, previous: OperatingMode) -> tuple[bool, str]:
        if previous is OperatingMode.BASE_MOTION:
            self._base_pub.publish(Twist())
            self._had_base_command = False
            return True, "Zero base velocity sent (not motion-confirmed)"
        if previous is OperatingMode.MANIPULATION:
            return self._hold_arms()
        if previous is OperatingMode.HEIGHT_ADJUST:
            if not self._stop_client.service_is_ready():
                return False, "Pedestal stop service unavailable"
            try:
                result = await self._stop_client.call_async(Trigger.Request())
            except Exception as exc:
                return False, f"Pedestal stop failed: {exc}"
            if not result.success:
                return False, f"Pedestal stop rejected: {result.message}"
            self._had_pedestal_command = False
            return True, "Pedestal stop acknowledged (not motion-confirmed)"
        return True, "No previously active subsystem"

    async def _set_mode(self, request, response):
        try:
            target = OperatingMode(request.mode.strip().lower())
        except ValueError:
            response.success = False
            response.message = f"Unknown operating mode: {request.mode}"
            response.current_mode = self._controller.mode.value
            return response

        if target is self._controller.mode:
            response.success = True
            response.message = "Already in requested mode"
            response.current_mode = target.value
            return response

        previous = self._controller.mode
        self._transitioning = True
        # Close the gate before requesting any stop, and before acknowledging
        # another active mode. NO_MOTION is always selectable.
        self._controller.set_mode(OperatingMode.NO_MOTION)
        self._publish_mode()
        try:
            stopped, reason = await self._stop_previous(previous)
            if stopped and target is not OperatingMode.NO_MOTION:
                self._controller.set_mode(target)
            response.success = stopped
            response.message = reason
            response.current_mode = self._controller.mode.value
            if not stopped:
                self.get_logger().error(
                    f"Exit action failed: {reason}; gate closed"
                )
        finally:
            self._transitioning = False
            self._publish_mode()
        return response

    def _publish_mode(self) -> None:
        self._mode_pub.publish(String(data=self._controller.mode.value))


def main(args=None) -> None:
    rclpy.init(args=args)
    node = CommandGateNode()
    executor = MultiThreadedExecutor(num_threads=2)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
