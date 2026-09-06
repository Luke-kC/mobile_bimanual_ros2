import rclpy
from controller_manager_msgs.msg import ControllerManagerActivity
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, qos_profile_sensor_data
from sensor_msgs.msg import JointState

from mobile_bimanual_control.core.models import (
    JointStateSnapshot,
)
from mobile_bimanual_control.core.supervisor import RobotSupervisor
from mobile_bimanual_control.core.supervisor_types import (
    ControllerID,
    HardwareID,
    LifecycleState,
    RobotMode,
    SupervisorStatus,
)
from mobile_bimanual_interfaces.msg import RobotStatus

ENUM_TO_MSG_MODE = {
    RobotMode.BOOTING: RobotStatus.MODE_BOOTING,
    RobotMode.INITIALIZING: RobotStatus.MODE_INITIALIZING,
    RobotMode.READY: RobotStatus.MODE_READY,
    RobotMode.DEGRADED: RobotStatus.MODE_DEGRADED,
    RobotMode.FAULT: RobotStatus.MODE_FAULT,
    RobotMode.ESTOP: RobotStatus.MODE_ESTOP,
}

MSG_TO_ENUM_MODE = {v: k for k, v in ENUM_TO_MSG_MODE.items()}


class SupervisorNode(Node):
    def __init__(self) -> None:
        super().__init__("supervisor_node")

        qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)

        self._supervisor: RobotSupervisor = RobotSupervisor()

        self._controller_manager_activity_sub = self.create_subscription(
            ControllerManagerActivity,
            "/controller_manager/activity",
            self._activity_callback,
            qos,
        )

        self._joint_state_sub = self.create_subscription(
            JointState,
            "/joint_states",
            self._joint_state_callback,
            qos_profile_sensor_data,
        )

        self._supervisor_timer = self.create_timer(
            0.01, self._supervisor_timer_callback
        )

        self._robot_status_pub = self.create_publisher(
            RobotStatus,
            "/mobile_bimanual/supervisor/robot_status",
            10,
        )

    def _activity_callback(self, msg: ControllerManagerActivity) -> None:

        hw_states: dict[HardwareID, LifecycleState] = {}
        for hw in msg.hardware_components:
            try:
                hw_id = HardwareID(hw.name)
                state = LifecycleState(hw.state.label)
                hw_states[hw_id] = state
            except ValueError:
                self.get_logger().warning(
                    f"Unknown hardware [{hw.name}] or unknown lifecycle [{hw.state.label}]"
                )

        self._supervisor.update_controller_manager_discovered_status(True)
        self._supervisor.update_hardware_state(hw_states)

        ctrl_states: dict[ControllerID, LifecycleState] = {}

        for ctrl in msg.controllers:
            try:
                ctrl_id = ControllerID(ctrl.name)
                state = LifecycleState(ctrl.state.label)
                ctrl_states[ctrl_id] = state
            except ValueError:
                self.get_logger().warning(
                    f"Unknown controller [{ctrl.name}] or unknown lifecycle [{ctrl.state.label}]"
                )

        self._supervisor.update_controller_state(ctrl_states)

    def _supervisor_timer_callback(self) -> None:
        status = self._supervisor.evaluate(self._now_sec())

        robot_status_msg = self._status_dataclass_to_msg(status)

        self._robot_status_pub.publish(robot_status_msg)

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

        self._supervisor.update_joint_state(snapshot)

    @staticmethod
    def _status_dataclass_to_msg(status: SupervisorStatus) -> RobotStatus:
        msg = RobotStatus()
        msg.mode = ENUM_TO_MSG_MODE[status.mode]
        msg.external_commands_allowed = status.external_commands_allowed
        msg.hardware_active = status.hardware_active
        msg.controllers_active = status.controllers_active
        msg.joint_state_complete = status.joint_state_complete
        msg.joint_state_fresh = status.joint_state_fresh
        msg.not_ready_components = list(status.not_ready_components)
        msg.active_faults = list(status.active_faults)
        return msg

    def _now_sec(self) -> float:
        return self.get_clock().now().nanoseconds / 1e9


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)

    node = SupervisorNode()

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
