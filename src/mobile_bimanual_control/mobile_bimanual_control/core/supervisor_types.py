from enum import Enum, StrEnum, auto
from dataclasses import dataclass


class HardwareID(StrEnum):
    RIGHT_ARM = "openarm_right_hardware_interface"
    LEFT_ARM = "openarm_left_hardware_interface"


class ControllerID(StrEnum):
    RIGHT_FORWARD_POS = "right_forward_position_controller"
    RIGHT_GRIPPER = "right_gripper_controller"
    LEFT_GRIPPER = "left_gripper_controller"
    LEFT_FORWARD_POS = "left_forward_position_controller"
    JOINT_STATE_BROADCASTER = "joint_state_broadcaster"


class LifecycleState(StrEnum):
    UNCONFIGURED = "unconfigured"
    INACTIVE = "inactive"
    ACTIVE = "active"
    FINALIZED = "finalized"


class RobotMode(Enum):
    BOOTING = auto()
    INITIALIZING = auto()
    READY = auto()
    DEGRADED = auto()
    FAULT = auto()
    ESTOP = auto()


@dataclass(frozen=True)
class SupervisorConfig:
    pass


@dataclass(frozen=True)
class SupervisorStatus:
    mode: RobotMode
    external_commands_allowed: bool

    hardware_active: bool
    controllers_active: bool
    joint_state_complete: bool
    joint_state_fresh: bool

    not_ready_components: tuple[str, ...]
    active_faults: tuple[str, ...]
