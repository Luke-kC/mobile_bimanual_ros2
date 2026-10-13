from __future__ import annotations

import math
import time

import rclpy
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.utilities import ok as rclpy_ok
from sensor_msgs.msg import JointState
from std_msgs.msg import Bool, Float64, String
from std_srvs.srv import Trigger

from mobile_bimanual_hardware.core.pedestal_serial import PedestalSerial


class PedestalNode(Node):
    def __init__(self) -> None:
        super().__init__("pedestal_node")

        self.declare_parameter("port", "/dev/pedestal")
        self.declare_parameter("publish_rate_hz", 20.0)
        self.declare_parameter("joint_name", "pedestal_joint")
        self.declare_parameter("telem_timeout_s", 0.3)
        self.declare_parameter("position_filter_tau_s", 0.25)

        port = str(self.get_parameter("port").value)
        publish_rate_hz = float(self.get_parameter("publish_rate_hz").value)

        self._telem_timeout_s = float(
            self.get_parameter("telem_timeout_s").value
        )
        self._position_filter_tau_s = float(
            self.get_parameter("position_filter_tau_s").value
        )

        if (
            not math.isfinite(self._telem_timeout_s)
            or self._telem_timeout_s <= 0.0
        ):
            raise ValueError("telem_timeout_s must be finite and positive")

        if publish_rate_hz <= 0.0:
            raise ValueError("publish_rate_hz must be positive")

        if (
            not math.isfinite(self._position_filter_tau_s)
            or self._position_filter_tau_s < 0.0
        ):
            raise ValueError(
                "position_filter_tau_s must be finite and non-negative"
            )

        self._joint_name = str(self.get_parameter("joint_name").value)

        self._pedestal = PedestalSerial(port)

        self.get_logger().info(f"Connected to pedestal on {port}")

        self._last_telemetry_time_sec: float | None = None
        self._last_event: str | None = None
        self._filtered_position_m: float | None = None
        self._last_filter_time_sec: float | None = None

        self._command_callback_group = MutuallyExclusiveCallbackGroup()
        self._telemetry_callback_group = MutuallyExclusiveCallbackGroup()

        # Absolute pedestal extension command in meters.
        self._target_sub = self.create_subscription(
            Float64,
            "/pedestal/position_target",
            self._target_callback,
            10,
            callback_group=self._command_callback_group,
        )

        self._stop_service = self.create_service(
            Trigger,
            "/pedestal/stop",
            self._stop_callback,
            callback_group=self._command_callback_group,
        )

        self._reset_fault_service = self.create_service(
            Trigger,
            "/pedestal/reset_fault",
            self._reset_fault_callback,
            callback_group=self._command_callback_group,
        )

        self._position_pub = self.create_publisher(
            Float64,
            "/pedestal/position",
            qos_profile_sensor_data,
        )

        self._validity_pub = self.create_publisher(
            Bool,
            "/pedestal/position_valid",
            qos_profile_sensor_data,
        )

        self._joint_state_pub = self.create_publisher(
            JointState,
            "/pedestal/joint_states",
            qos_profile_sensor_data,
        )

        self._sensor_voltage_pub = self.create_publisher(
            Float64,
            "/pedestal/sensor_voltage",
            qos_profile_sensor_data,
        )

        self._goal_active_pub = self.create_publisher(
            Bool,
            "/pedestal/goal_active",
            qos_profile_sensor_data,
        )

        self._task_state_pub = self.create_publisher(
            String,
            "/pedestal/task_state",
            qos_profile_sensor_data,
        )

        self._unlocked_pub = self.create_publisher(
            Bool,
            "/pedestal/unlocked",
            qos_profile_sensor_data,
        )

        self._telemetry_timer = self.create_timer(
            1.0 / publish_rate_hz,
            self._telemetry_timer_callback,
            callback_group=self._telemetry_callback_group,
        )

    def _target_callback(self, msg: Float64) -> None:
        position_m = float(msg.data)

        if not math.isfinite(position_m):
            self.get_logger().warning(
                "Rejected non-finite pedestal position target"
            )
            return

        if self._pedestal.set_target(position_m):
            self.get_logger().info(
                f"Accepted pedestal target: {position_m:.4f} m"
            )
        else:
            self.get_logger().warning(
                f"Pedestal rejected target: {position_m:.4f} m"
            )

    def _stop_callback(
        self,
        request: Trigger.Request,
        response: Trigger.Response,
    ) -> Trigger.Response:
        del request

        response.success = self._pedestal.stop()
        response.message = (
            "stop accepted" if response.success else "stop failed"
        )

        return response

    def _reset_fault_callback(
        self,
        request: Trigger.Request,
        response: Trigger.Response,
    ) -> Trigger.Response:
        del request

        response.success = self._pedestal.reset_fault()
        response.message = (
            "fault reset" if response.success else "fault reset failed"
        )

        return response

    def _telemetry_timer_callback(self) -> None:
        self._log_new_event()

        telemetry = self._pedestal.latest_telemetry

        position_valid = False
        telemetry_fresh = False

        if telemetry is not None:
            telemetry_age_s = time.monotonic() - telemetry.received_time_sec

            telemetry_fresh = 0.0 <= telemetry_age_s < self._telem_timeout_s

            position_valid = (
                telemetry_fresh and telemetry.position_m is not None
            )

        validity_msg = Bool()
        validity_msg.data = position_valid
        self._validity_pub.publish(validity_msg)

        if telemetry is None or not telemetry_fresh:
            return

        if self._last_telemetry_time_sec == telemetry.received_time_sec:
            return

        self._last_telemetry_time_sec = telemetry.received_time_sec

        stamp = self.get_clock().now().to_msg()

        if telemetry.position_m is not None:
            filtered_position_m = self._filter_position(
                telemetry.position_m,
                telemetry.received_time_sec,
            )

            position_msg = Float64()
            position_msg.data = filtered_position_m
            self._position_pub.publish(position_msg)

            joint_state_msg = JointState()
            joint_state_msg.header.stamp = stamp
            joint_state_msg.name = [self._joint_name]
            joint_state_msg.position = [filtered_position_m]
            self._joint_state_pub.publish(joint_state_msg)

        if telemetry.sensor_voltage_v is not None:
            voltage_msg = Float64()
            voltage_msg.data = telemetry.sensor_voltage_v
            self._sensor_voltage_pub.publish(voltage_msg)

        goal_msg = Bool()
        goal_msg.data = telemetry.goal_active
        self._goal_active_pub.publish(goal_msg)

        task_state_msg = String()
        task_state_msg.data = telemetry.task_state
        self._task_state_pub.publish(task_state_msg)

        unlocked_msg = Bool()
        unlocked_msg.data = telemetry.unlocked
        self._unlocked_pub.publish(unlocked_msg)

    def _filter_position(
        self,
        raw_position_m: float,
        sample_time_sec: float,
    ) -> float:
        if self._position_filter_tau_s == 0.0:
            self._filtered_position_m = raw_position_m
            self._last_filter_time_sec = sample_time_sec
            return raw_position_m

        if (
            self._filtered_position_m is None
            or self._last_filter_time_sec is None
        ):
            self._filtered_position_m = raw_position_m
            self._last_filter_time_sec = sample_time_sec
            return raw_position_m

        dt_s = sample_time_sec - self._last_filter_time_sec
        self._last_filter_time_sec = sample_time_sec

        if dt_s <= 0.0:
            return self._filtered_position_m

        alpha = dt_s / (self._position_filter_tau_s + dt_s)
        self._filtered_position_m += alpha * (
            raw_position_m - self._filtered_position_m
        )

        return self._filtered_position_m

    def _log_new_event(self) -> None:
        event = self._pedestal.last_event

        if event is None or event == self._last_event:
            return

        self._last_event = event

        if event.startswith("FAULT "):
            self.get_logger().error(f"Pedestal {event}")
        elif event == "GOAL_REACHED":
            self.get_logger().info("Pedestal goal reached")
        else:
            self.get_logger().info(f"Pedestal event: {event}")

    def destroy_node(self) -> None:
        self._pedestal.close()
        super().destroy_node()


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)

    node = PedestalNode()

    executor = MultiThreadedExecutor(num_threads=2)
    executor.add_node(node)

    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown()
        node.destroy_node()

        if rclpy_ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
