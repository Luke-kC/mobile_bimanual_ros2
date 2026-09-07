from pathlib import Path

import mink
import mujoco
import numpy as np

MODEL_PATH = (
    Path(__file__).resolve().parent.parent
    / "mobile_bimanual_description"
    / "mujoco"
    / "yam_v1"
    / "yam.xml"
)


def main() -> None:
    model = mujoco.MjModel.from_xml_path(str(MODEL_PATH))  # pyright: ignore

    configuration = mink.Configuration(model)

    velocity_limits = {
        "joint1": 1.0,
        "joint2": 1.0,
        "joint3": 1.0,
        "joint4": 1.0,
        "joint5": 1.0,
        "joint6": 1.0,
    }

    limits = [
        mink.ConfigurationLimit(model),
        mink.VelocityLimit(
            model,
            velocity_limits,
        ),
    ]

    q_initial = np.array(
        [
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
        ]
    )

    configuration.update(q_initial)

    task = mink.FrameTask(
        frame_name="gripper",
        frame_type="body",
        position_cost=1.0,
        orientation_cost=1.0,
    )

    current_pose = configuration.get_transform_frame_to_world(
        "gripper",
        "body",
    )

    target_matrix = current_pose.as_matrix().copy()

    # Move target 25 cm along world axis.
    target_matrix[0, 3] += 0.25
    target_matrix[1, 3] += 0.0
    target_matrix[2, 3] += 0.0

    task.set_target(mink.SE3.from_matrix(target_matrix))

    dt = 0.01

    for iteration in range(1000):
        velocity = mink.solve_ik(
            configuration,
            [task],
            dt,
            solver="daqp",
            damping=1e-3,
            limits=limits,
        )

        configuration.integrate_inplace(
            velocity,
            dt,
        )

        error = task.compute_error(configuration)

        position_error_m = np.linalg.norm(error[:3])
        orientation_error_rad = np.linalg.norm(error[3:])

        if position_error_m < 1e-4 and orientation_error_rad < 1e-3:
            print(f"Converged after {iteration + 1} iterations")
            break

    print("q initial:")
    print(q_initial)

    print("q solution:")
    print(configuration.q)

    print("final pose:")
    print(
        configuration.get_transform_frame_to_world(
            "gripper",
            "body",
        ).as_matrix()
    )


if __name__ == "__main__":
    main()
