RIGHT_ARM_JOINTS: list[str] = [
    "openarm_right_joint1",
    "openarm_right_joint2",
    "openarm_right_joint3",
    "openarm_right_joint4",
    "openarm_right_joint5",
    "openarm_right_joint6",
    "openarm_right_joint7",
]

LEFT_ARM_JOINTS: list[str] = [
    "openarm_left_joint1",
    "openarm_left_joint2",
    "openarm_left_joint3",
    "openarm_left_joint4",
    "openarm_left_joint5",
    "openarm_left_joint6",
    "openarm_left_joint7",
]

RIGHT_GRIPPER_JOINT: str = "openarm_right_finger_joint1"
LEFT_GRIPPER_JOINT: str = "openarm_left_finger_joint1"

ARM_JOINTS: list[str] = RIGHT_ARM_JOINTS + LEFT_ARM_JOINTS

ALL_JOINTS = ARM_JOINTS + [
    RIGHT_GRIPPER_JOINT,
    LEFT_GRIPPER_JOINT,
]

JOINT_LIMITS = {
    # Right arm
    "openarm_right_joint1": (-1.3963, 3.4907),
    "openarm_right_joint2": (-0.17453, 3.3161),
    "openarm_right_joint3": (-1.5708, 1.5708),
    "openarm_right_joint4": (0.0, 2.4435),
    "openarm_right_joint5": (-1.5708, 1.5708),
    "openarm_right_joint6": (-0.7854, 0.7854),
    "openarm_right_joint7": (-1.5708, 1.5708),
    # Left arm
    "openarm_left_joint1": (-3.4907, 1.3963),
    "openarm_left_joint2": (-3.3161, 0.17453),
    "openarm_left_joint3": (-1.5708, 1.5708),
    "openarm_left_joint4": (0.0, 2.4435),
    "openarm_left_joint5": (-1.5708, 1.5708),
    "openarm_left_joint6": (-0.7854, 0.7854),
    "openarm_left_joint7": (-1.5708, 1.5708),
}
