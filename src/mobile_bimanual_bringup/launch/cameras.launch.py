"""Standalone three-camera bringup, independent of robot hardware bringup."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description() -> LaunchDescription:
    share = FindPackageShare("mobile_bimanual_bringup")

    def config(filename):
        return PathJoinSubstitution([share, "config", "cameras", filename])

    realsense = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare("realsense2_camera"), "launch", "rs_launch.py"
            ])
        ),
        launch_arguments={
            "camera_namespace": "camera",
            "camera_name": "camera",
            "config_file": config("realsense.yaml"),
        }.items(),
        condition=IfCondition(LaunchConfiguration("enable_realsense")),
    )

    oak = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare("depthai_ros_driver"), "launch", "camera.launch.py"
            ])
        ),
        launch_arguments={"params_file": config("oak.yaml")}.items(),
        condition=IfCondition(LaunchConfiguration("enable_oak")),
    )

    zed = Node(
        package="usb_cam",
        executable="usb_cam_node_exe",
        namespace="cameras/head_stereo",
        name="usb_cam",
        output="screen",
        parameters=[config("zed.yaml"), {
            "video_device": LaunchConfiguration("zed_device"),
        }],
        condition=IfCondition(LaunchConfiguration("enable_zed")),
    )

    head_left = Node(
        package="mobile_bimanual_bringup",
        executable="zed_left_image",
        namespace="cameras/head",
        name="zed_left_image",
        output="screen",
        parameters=[{
            "input_topic": "/cameras/head_stereo/image_raw",
            "output_topic": "/cameras/head/image_raw",
            "output_frame_id": LaunchConfiguration("head_left_frame_id"),
        }],
        condition=IfCondition(LaunchConfiguration("enable_zed")),
    )

    return LaunchDescription([
        DeclareLaunchArgument("enable_realsense", default_value="true"),
        DeclareLaunchArgument("enable_oak", default_value="true"),
        DeclareLaunchArgument("enable_zed", default_value="true"),
        DeclareLaunchArgument(
            "zed_device", default_value="/dev/video0",
            description="ZED UVC image device (prefer /dev/v4l/by-id/...-video-index0)",
        ),
        DeclareLaunchArgument(
            "head_left_frame_id", default_value="zed2i_left_optical_frame",
            description="TF frame for the extracted left optical image; publish its TF separately",
        ),
        realsense,
        oak,
        zed,
        head_left,
    ])
