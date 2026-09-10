import numpy as np
from geometry_msgs.msg import TransformStamped
from scipy.spatial.transform import Rotation


def transform_stamped_to_homogeneous(tf: TransformStamped) -> np.ndarray:
    p = np.array(
        [
            tf.transform.translation.x,
            tf.transform.translation.y,
            tf.transform.translation.z,
        ]
    )
    R = Rotation.from_quat(
        [
            tf.transform.rotation.x,
            tf.transform.rotation.y,
            tf.transform.rotation.z,
            tf.transform.rotation.w,
        ]
    )

    T: np.ndarray = np.eye(4)
    T[0:3, 0:3] = R.as_matrix()
    T[0:3, 3] = p
    return T
