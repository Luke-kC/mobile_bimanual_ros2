import time
from pathlib import Path

import mujoco
import mujoco.viewer


MODEL_PATH = (
    Path(__file__).resolve().parent.parent
    / "mobile_bimanual_description"
    / "mujoco"
    / "yam_v1"
    / "yam_table.xml"
)


def reset(model: mujoco.MjModel, data: mujoco.MjData) -> None:
    mujoco.mj_resetData(model, data)


def main() -> None:
    model = mujoco.MjModel.from_xml_path(str(MODEL_PATH))
    data = mujoco.MjData(model)

    print("nq =", model.nq)
    print("nv =", model.nv)
    print("nu =", model.nu)

    for i in range(model.njnt):
        print(
            model.joint(i).name,
            model.jnt_qposadr[i],
        )

    keyframe_id = model.key("home").id

    mujoco.mj_resetDataKeyframe(
        model,
        data,
        keyframe_id,
    )

    print("qpos =", data.qpos)
    print("ctrl =", data.ctrl)

    with mujoco.viewer.launch_passive(model, data) as viewer:
        while viewer.is_running():
            loop_start = time.time()

            mujoco.mj_step(model, data)
            viewer.sync()

            remaining = model.opt.timestep - (time.time() - loop_start)

            if remaining > 0:
                time.sleep(remaining)


if __name__ == "__main__":
    main()
