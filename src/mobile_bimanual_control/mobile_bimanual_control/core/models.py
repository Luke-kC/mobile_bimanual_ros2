from dataclasses import dataclass


# Controller related
@dataclass(frozen=True)
class ControllerConfig:
    command_rate_hz: float
    joint_state_timeout_sec: float
    max_velocity_rad_s: float
    max_target_step_rad: float
    max_tracking_error_rad: float


@dataclass(frozen=True)
class JointStateSnapshot:
    positions: dict[str, float]
    velocities: dict[str, float]
    efforts: dict[str, float]
    received_time_sec: float


@dataclass(frozen=True)
class JointTarget:
    positions: dict[str, float]


@dataclass(frozen=True)
class TargetResult:
    accepted: bool
    reason: str | None = None


@dataclass(frozen=True)
class StepResult:
    command_positions: dict[str, float] | None = None

    state_became_stale: bool = False
    state_recovered: bool = False

    tracking_fault_activated: bool = False
    tracking_fault_recovered: bool = False

    fault_joint: str | None = None
    tracking_error_rad: float | None = None
