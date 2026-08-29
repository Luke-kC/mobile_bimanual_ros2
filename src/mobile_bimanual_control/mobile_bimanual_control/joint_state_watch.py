import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState


class JointStateWatch(Node):
    def __init__(self) -> None:
        super().__init__('joint_state_watch')
        self.create_subscription(JointState, '/joint_states', self._on_joint_state, 10)
        self._seen = False

    def _on_joint_state(self, msg: JointState) -> None:
        if not self._seen:
            self.get_logger().info(f'Received {len(msg.name)} joints on /joint_states')
            self._seen = True


def main(args=None) -> None:
    rclpy.init(args=args)
    node = JointStateWatch()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
