import time
from pathlib import Path

import mujoco
import mujoco.viewer


MODEL_PATH = (
    Path(__file__).resolve().parent.parent
    / "mobile_bimanual_description"
    / "mujoco"
    / "yam_v1"
    / "yam_position.xml"
)


def reset(model: mujoco.MjModel, data: mujoco.MjData) -> None:
    mujoco.mj_resetData(model, data)


def main() -> None:

    t0 = time.time()

    model = mujoco.MjModel.from_xml_path(str(MODEL_PATH))
    data = mujoco.MjData(model)

    print("nq =", model.nq)
    print("nv =", model.nv)
    print("nu =", model.nu)

    target = 1
    joint1 = model.actuator("joint1")

    with mujoco.viewer.launch_passive(model, data) as viewer:
        while viewer.is_running():
            loop_start = time.time()

            data.ctrl[joint1.id] = target

            mujoco.mj_step(model, data)

            viewer.sync()

            remaining = model.opt.timestep - (time.time() - loop_start)

            if remaining > 0:
                time.sleep(remaining)


if __name__ == "__main__":
    main()
