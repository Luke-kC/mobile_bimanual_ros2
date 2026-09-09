import time
from pathlib import Path

import mujoco
import mujoco.viewer

MODEL_PATH = (
    Path(__file__).resolve().parent.parent
    / "openarm_mujoco"
    / "v1"
    / "openarm_bimanual.xml"
)


def set_joint_position(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    joint_name: str,
    position_rad: float,
) -> None:
    joint_id = mujoco.mj_name2id(
        model,
        mujoco.mjtObj.mjOBJ_JOINT,
        joint_name,
    )

    qpos_addr = model.jnt_qposadr[joint_id]
    data.qpos[qpos_addr] = position_rad

    mujoco.mj_forward(model, data)


def main() -> None:
    model = mujoco.MjModel.from_xml_path(str(MODEL_PATH))
    data = mujoco.MjData(model)

    print(f"model: {MODEL_PATH}")
    print(f"nq = {model.nq}")
    print(f"nv = {model.nv}")
    print(f"nu = {model.nu}")

    print("\nJoints:")
    for joint_id in range(model.njnt):
        joint = model.joint(joint_id)

        print(
            f"{joint_id:2d}: "
            f"{joint.name:35s} "
            f"qpos_addr={model.jnt_qposadr[joint_id]}"
        )

    print("\nActuators:")
    for actuator_id in range(model.nu):
        actuator = model.actuator(actuator_id)

        print(f"{actuator_id:2d}: {actuator.name}")

    set_joint_position(
        model,
        data,
        "openarm_right_joint3",
        0.1,
    )

    with mujoco.viewer.launch_passive(model, data) as viewer:
        while viewer.is_running():
            loop_start = time.time()

            mujoco.mj_step(model, data)
            viewer.sync()

            remaining_sec = model.opt.timestep - (time.time() - loop_start)

            if remaining_sec > 0.0:
                time.sleep(remaining_sec)


if __name__ == "__main__":
    main()
