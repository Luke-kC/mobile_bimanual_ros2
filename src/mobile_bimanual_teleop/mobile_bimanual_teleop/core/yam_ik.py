from dataclasses import dataclass
from pathlib import Path

import mink
import mujoco
import numpy as np
from mink.exceptions import NoSolutionFound

MAX_ITERATIONS = 200
IK_DT_SEC = 0.01


@dataclass(frozen=True)
class IKResult:
    q: np.ndarray | None = None
    converged: bool = False
    iterations: int = 0
    position_error_m: float | None = None
    orientation_error_rad: float | None = None


class YamIK:
    def __init__(self, model_path: Path) -> None:
        self._model = mujoco.MjModel.from_xml_path(str(model_path))  # pyright: ignore
        self._configuration = mink.Configuration(self._model)

        self._ik_step_limits = {
            "joint1": 1.0,
            "joint2": 1.0,
            "joint3": 1.0,
            "joint4": 1.0,
            "joint5": 1.0,
            "joint6": 1.0,
        }

        self._limits = [
            mink.ConfigurationLimit(self._model),
            mink.VelocityLimit(
                self._model,
                self._ik_step_limits,
            ),
        ]

        self._task = mink.FrameTask(
            frame_name="gripper",
            frame_type="body",
            position_cost=1.0,
            orientation_cost=0.2,
        )

        self._current_yam_q: np.ndarray | None = None

    def current_gripper_pose(self) -> np.ndarray | None:
        if self._current_yam_q is None:
            return

        self._configuration.update(q=self._current_yam_q)

        return (
            self._configuration.get_transform_frame_to_world(
                "gripper",
                "body",
            )
            .as_matrix()
            .copy()
        )

    def update_current_yam_q(self, q: np.ndarray) -> None:
        self._current_yam_q = q.copy()

    def solve(self, target: np.ndarray) -> IKResult:

        if self._current_yam_q is None:
            return IKResult()

        self._configuration.update(q=self._current_yam_q)
        self._task.set_target(mink.SE3.from_matrix(target))

        try:
            for iteration in range(MAX_ITERATIONS):
                velocity = mink.solve_ik(
                    self._configuration,
                    [self._task],
                    dt=IK_DT_SEC,
                    solver="daqp",
                    limits=self._limits,
                    damping=1e-3,
                )

                self._configuration.integrate_inplace(
                    velocity,
                    IK_DT_SEC,
                )

                error = self._task.compute_error(self._configuration)

                position_error_m = float(np.linalg.norm(error[:3]))
                orientation_error_rad = float(np.linalg.norm(error[3:]))

                if position_error_m < 1e-4 and orientation_error_rad < 1e-3:
                    return IKResult(
                        q=self._configuration.q.copy(),
                        converged=True,
                        iterations=iteration + 1,
                        position_error_m=position_error_m,
                        orientation_error_rad=orientation_error_rad,
                    )

            return IKResult(
                q=self._configuration.q.copy(),
                converged=False,
                iterations=MAX_ITERATIONS,
                position_error_m=position_error_m,
                orientation_error_rad=orientation_error_rad,
            )

        except NoSolutionFound:
            return IKResult()
