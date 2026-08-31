import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState


class JointStateWatchNode(Node):
    def __init__(self) -> None:
        super().__init__("joint_state_watch")

        self._seen = False

        self.create_subscription(
            JointState,
            "/joint_states",
            self._joint_state_callback,
            10,
        )

    def _joint_state_callback(
        self,
        msg: JointState,
    ) -> None:
        if self._seen:
            return

        self.get_logger().info(
            f"Received {len(msg.name)} joints on /joint_states"
        )

        self._seen = True


def main(
    args: list[str] | None = None,
) -> None:
    rclpy.init(args=args)

    node = JointStateWatchNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
