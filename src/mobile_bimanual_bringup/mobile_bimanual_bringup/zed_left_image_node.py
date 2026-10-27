"""ROS 2 image cropper for the ZED 2i UVC stereo side-by-side output."""

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image

from mobile_bimanual_bringup.zed_left_crop import left_half_packed


class ZedLeftImageNode(Node):
    def __init__(self):
        super().__init__("zed_left_image")
        self.declare_parameter("input_topic", "/cameras/head_stereo/image_raw")
        self.declare_parameter("output_topic", "/cameras/head/image_raw")
        self.declare_parameter("output_frame_id", "zed2i_left_optical_frame")
        input_topic = self.get_parameter("input_topic").value
        output_topic = self.get_parameter("output_topic").value
        self._frame_id = self.get_parameter("output_frame_id").value
        self._pub = self.create_publisher(Image, output_topic, qos_profile_sensor_data)
        self._sub = self.create_subscription(
            Image, input_topic, self._on_image, qos_profile_sensor_data
        )
        self._errors = 0
        self.get_logger().info(f"Cropping left image: {input_topic} -> {output_topic}")

    def _on_image(self, msg: Image):
        try:
            width, step, payload = left_half_packed(
                msg.data, width=msg.width, height=msg.height,
                step=msg.step, encoding=msg.encoding,
            )
        except ValueError as exc:
            self._errors += 1
            if self._errors <= 3 or self._errors % 100 == 0:
                self.get_logger().error(f"ZED crop rejected frame: {exc}")
            return

        out = Image()
        out.header.stamp = msg.header.stamp
        out.header.frame_id = self._frame_id
        out.height = msg.height
        out.width = width
        out.encoding = msg.encoding
        out.is_bigendian = msg.is_bigendian
        out.step = step
        out.data = payload
        self._pub.publish(out)


def main(args=None):
    rclpy.init(args=args)
    node = ZedLeftImageNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
