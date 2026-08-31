from __future__ import annotations

import math

from mobile_bimanual_control.core.joints import (
    ARM_JOINTS,
    JOINT_LIMITS,
)
from mobile_bimanual_control.core.models import (
    ControllerConfig,
    JointStateSnapshot,
    JointTarget,
    StepResult,
    TargetResult,
)


class BimanualController:
    def __init__(self, config: ControllerConfig) -> None:
        self._config: ControllerConfig = config

        self._state: JointStateSnapshot | None = None

        self._command_positions: dict[str, float] = {}
        self._target_positions: dict[str, float] = {}

        self._initialized: bool = False
        self._state_stale: bool = False
        self._tracking_fault: bool = False

    @property
    def initialized(self) -> bool:
        return self._initialized

    @property
    def measured_positions(self) -> dict[str, float]:
        if self._state is None:
            return {}

        return dict(self._state.positions)

    @property
    def command_positions(self) -> dict[str, float]:
        return dict(self._command_positions)

    def update_state(
        self,
        state: JointStateSnapshot,
    ) -> bool:
        self._state = state

        if self._initialized:
            return False

        if not self._has_complete_arm_state():
            return False

        self._command_positions = {
            joint: state.positions[joint] for joint in ARM_JOINTS
        }

        self._target_positions = dict(self._command_positions)

        self._initialized = True

        return True

    def set_target(
        self,
        target: JointTarget,
        now_sec: float,
    ) -> TargetResult:
        if not self._initialized:
            return TargetResult(
                accepted=False,
                reason="command state is not initialized",
            )

        if not self._state_is_fresh(now_sec):
            return TargetResult(
                accepted=False,
                reason="joint state is stale",
            )

        if self._tracking_fault:
            return TargetResult(
                accepted=False,
                reason="tracking fault is active",
            )

        if not target.positions:
            return TargetResult(accepted=False, reason="no joints specified")

        for (
            joint,
            position,
        ) in target.positions.items():
            result = self._validate_joint_target(
                joint,
                position,
            )

            if result is not None:
                return TargetResult(
                    accepted=False,
                    reason=result,
                )

        self._target_positions.update(target.positions)

        return TargetResult(accepted=True)

    def step(
        self,
        now_sec: float,
    ) -> StepResult:
        if not self._initialized:
            return StepResult()

        if not self._state_is_fresh(now_sec):
            became_stale = not self._state_stale
            self._state_stale = True

            return StepResult(state_became_stale=became_stale)

        state_recovered = self._state_stale
        self._state_stale = False

        fault = self._find_tracking_fault()

        if fault is not None:
            joint, error = fault

            fault_activated = not self._tracking_fault
            self._tracking_fault = True

            return StepResult(
                state_recovered=state_recovered,
                tracking_fault_activated=fault_activated,
                fault_joint=joint,
                tracking_error_rad=error,
            )

        tracking_recovered = self._tracking_fault
        self._tracking_fault = False

        self._update_command_positions()

        return StepResult(
            command_positions=dict(self._command_positions),
            state_recovered=state_recovered,
            tracking_fault_recovered=tracking_recovered,
        )

    def _has_complete_arm_state(self) -> bool:
        if self._state is None:
            return False

        return all(joint in self._state.positions for joint in ARM_JOINTS)

    def _state_is_fresh(
        self,
        now_sec: float,
    ) -> bool:
        if self._state is None:
            return False

        age_sec = now_sec - self._state.received_time_sec

        return 0.0 <= age_sec < self._config.joint_state_timeout_sec

    def _validate_joint_target(
        self,
        joint: str,
        position: float,
    ) -> str | None:
        if joint not in ARM_JOINTS:
            return f"unknown/unsupported joint '{joint}'"

        if not math.isfinite(position):
            return f"non-finite positions for '{joint}'"

        lower, upper = JOINT_LIMITS[joint]

        if position < lower or position > upper:
            return (
                f"'{joint}' position {position:+.4f} rad is "
                f"outside [{lower:+.4f}, {upper:+.4f}]"
            )

        command = self._command_positions[joint]

        target_step = abs(position - command)

        if target_step > self._config.max_target_step_rad:
            return (
                f"'{joint}' step {target_step:.4f} rad exceeds "
                f"{self._config.max_target_step_rad:.4f} rad"
            )

        return None

    def _update_command_positions(self) -> None:
        max_step = (
            self._config.max_velocity_rad_s / self._config.command_rate_hz
        )

        for joint in ARM_JOINTS:
            command = self._command_positions[joint]
            target = self._target_positions[joint]

            error = target - command

            if abs(error) <= max_step:
                self._command_positions[joint] = target
            elif error > 0.0:
                self._command_positions[joint] = command + max_step
            else:
                self._command_positions[joint] = command - max_step

    def _find_tracking_fault(
        self,
    ) -> tuple[str, float] | None:
        assert self._state is not None

        for joint in ARM_JOINTS:
            error = abs(
                self._command_positions[joint] - self._state.positions[joint]
            )

            if error > self._config.max_tracking_error_rad:
                return joint, error

        return None
