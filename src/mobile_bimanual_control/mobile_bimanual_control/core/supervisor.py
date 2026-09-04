from mobile_bimanual_control.core.models import JointStateSnapshot
from mobile_bimanual_control.core.joints import ARM_JOINTS
from mobile_bimanual_control.core.supervisor_types import (
    SupervisorStatus,
    SupervisorConfig,
    RobotMode,
    HardwareID,
    ControllerID,
    LifecycleState,
)


class RobotSupervisor:
    def __init__(self) -> None:
        self._hardware_state: dict[HardwareID, LifecycleState] = {
            hw: LifecycleState.INACTIVE for hw in HardwareID
        }

        self._controller_state: dict[ControllerID, LifecycleState] = {
            controller: LifecycleState.INACTIVE for controller in ControllerID
        }

        self._joint_state: JointStateSnapshot | None = None
        self._controller_manager_discovered: bool = False
        self._last_eval_sec: float | None = None

    def update_controller_manager_discovered_status(
        self, discovered: bool
    ) -> None:
        self._controller_manager_discovered = discovered

    def update_hardware_state(
        self,
        states: dict[HardwareID, LifecycleState],
    ) -> None:
        for hardware, lifecycle_state in states.items():
            self._hardware_state[hardware] = lifecycle_state

    def update_controller_state(
        self,
        states: dict[ControllerID, LifecycleState],
    ) -> None:
        for controller, lifecycle_state in states.items():
            self._controller_state[controller] = lifecycle_state

    def update_joint_state(
        self,
        state: JointStateSnapshot,
    ) -> None:
        self._joint_state = state

    def evaluate(
        self,
        now_sec: float,
    ) -> SupervisorStatus:

        robot_mode = RobotMode.BOOTING
        external_commands_allowed: bool = False
        controller_active: bool = False
        self._last_eval_sec = now_sec

        if self._controller_manager_discovered:
            robot_mode = RobotMode.INITIALIZING

        hardware_active = all(
            self._hardware_state[hardware] == LifecycleState.ACTIVE
            for hardware in HardwareID
        )

        controller_active = all(
            self._controller_state[controller] == LifecycleState.ACTIVE
            for controller in ControllerID
        )

        joint_state_complete = self._has_complete_arm_state()

        if (
            self._controller_manager_discovered
            and hardware_active
            and controller_active
            and joint_state_complete
            and self._joint_state_is_fresh(now_sec)
        ):
            robot_mode = RobotMode.READY

        if robot_mode == RobotMode.READY:
            external_commands_allowed = True

        not_ready: list[str] = []
        for hw, state in self._hardware_state.items():
            if state != LifecycleState.ACTIVE:
                not_ready.append(f"hw:{hw}")
        for ctrl, state in self._controller_state.items():
            if state != LifecycleState.ACTIVE:
                not_ready.append(f"ctrl:{ctrl}")

        supervisor_status: SupervisorStatus = SupervisorStatus(
            mode=robot_mode,
            external_commands_allowed=external_commands_allowed,
            hardware_active=hardware_active,
            controllers_active=controller_active,
            joint_state_complete=joint_state_complete,
            joint_state_fresh=self._joint_state_is_fresh(now_sec),
            not_ready_components=tuple(not_ready),
            active_faults=tuple(),
        )

        return supervisor_status

    def _has_complete_arm_state(self) -> bool:
        if self._joint_state is None:
            return False

        if self._last_eval_sec is None:
            return False

        return all(
            joint in self._joint_state.positions for joint in ARM_JOINTS
        ) and self._joint_state_is_fresh(self._last_eval_sec)

    def _joint_state_is_fresh(self, now_sec: float) -> bool:
        if self._joint_state is None:
            return False

        return (now_sec - self._joint_state.received_time_sec) < 0.1
