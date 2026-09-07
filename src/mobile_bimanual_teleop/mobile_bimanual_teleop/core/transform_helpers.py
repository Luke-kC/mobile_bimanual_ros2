import numpy as np
from scipy.spatial.transform import Rotation


def map_spatial_motion(
    leader_ref: np.ndarray,
    leader_cur: np.ndarray,
    follower_ref: np.ndarray,
) -> np.ndarray:
    delta_p = leader_cur[:3, 3] - leader_ref[:3, 3]

    delta_R = leader_cur[:3, :3] @ leader_ref[:3, :3].T

    follower_des = np.eye(4)

    follower_des[:3, 3] = follower_ref[:3, 3] + delta_p

    follower_des[:3, :3] = delta_R @ follower_ref[:3, :3]

    return follower_des
