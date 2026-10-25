"""Publish filtered Tracer odometry and the sole public odometry transform."""

import json
import math
from dataclasses import fields

import rclpy
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import String
from tf2_ros import TransformBroadcaster

from mobile_bimanual_bringup.odometry_filter import FilterConfig, OdometryFilter


class FilteredOdometry(Node):
    def __init__(self):
        super().__init__("filtered_odometry")
        defaults = FilterConfig()
        config = FilterConfig(**{
            field.name: self.declare_parameter(field.name, getattr(defaults, field.name)).value
            for field in fields(defaults)
        })
        self.filter = OdometryFilter(config)
        self.odom_frame = self.declare_parameter("odom_frame", "odom").value
        self.base_frame = self.declare_parameter("base_frame", "base_link").value
        self.publisher = self.create_publisher(Odometry, "/odom", 10)
        self.status = self.create_publisher(String, "/odom/filter_status", 10)
        self.broadcaster = TransformBroadcaster(self)
        self.subscription = self.create_subscription(Odometry, "/odom/raw", self.receive, 10)
        self.last_received = None
        self.timed_out = False
        self.uncertainty = 0.0
        self.create_timer(0.05, self.check_timeout)

    def receive(self, msg):
        now = self.get_clock().now()
        stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        age = now.nanoseconds * 1e-9 - stamp
        if age > self.filter.config.feedback_timeout or age < -0.05:
            self.report("stale or future feedback timestamp")
            return
        accepted, reason = self.filter.update(
            stamp, msg.twist.twist.linear.x, msg.twist.twist.angular.z
        )
        if reason in ("invalid timestamp", "non-increasing timestamp"):
            self.report(reason)
            return
        self.last_received = now
        self.timed_out = False
        if not accepted:
            self.uncertainty += 0.001
            self.get_logger().warning(f"Rejected odometry feedback: {reason}", throttle_duration_sec=2.0)
        self.publish(msg.header.stamp, not accepted)
        self.report(reason)

    def check_timeout(self):
        if self.last_received is None:
            return
        now = self.get_clock().now()
        elapsed = (now - self.last_received).nanoseconds * 1e-9
        if elapsed < 0 or elapsed > self.filter.config.feedback_timeout:
            if not self.timed_out:
                self.filter.expire()
                self.uncertainty += 0.01
                self.timed_out = True
                self.get_logger().warning("Odometry feedback timed out; holding pose")
            self.publish(now.to_msg(), True)
            self.report("feedback timeout")

    def publish(self, stamp, degraded):
        f = self.filter
        msg = Odometry()
        msg.header.stamp = stamp
        msg.header.frame_id = self.odom_frame
        msg.child_frame_id = self.base_frame
        msg.pose.pose.position.x, msg.pose.pose.position.y = f.x, f.y
        msg.pose.pose.orientation.z = math.sin(f.yaw / 2)
        msg.pose.pose.orientation.w = math.cos(f.yaw / 2)
        msg.twist.twist.linear.x, msg.twist.twist.angular.z = f.linear, f.angular
        for index in (0, 7, 35):
            msg.pose.covariance[index] = 0.01 + self.uncertainty
            msg.twist.covariance[index] = 0.1 if degraded else 0.01
        for index in (14, 21, 28):
            msg.pose.covariance[index] = 1e6
            msg.twist.covariance[index] = 1e6
        transform = TransformStamped()
        transform.header = msg.header
        transform.child_frame_id = msg.child_frame_id
        transform.transform.translation.x = f.x
        transform.transform.translation.y = f.y
        transform.transform.rotation = msg.pose.pose.orientation
        self.publisher.publish(msg)
        self.broadcaster.sendTransform(transform)

    def report(self, reason):
        self.status.publish(String(data=json.dumps({
            "state": reason,
            "rejected_count": self.filter.rejected_count,
        })))


def main(args=None):
    rclpy.init(args=args)
    node = FilteredOdometry()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
