"""Opt-in gated hardware bringup. Existing public command topic names remain unchanged."""

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    GroupAction,
    IncludeLaunchDescription,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node, SetRemap
from launch_ros.substitutions import FindPackageShare

COMMAND_TOPICS = (
    "/cmd_vel",
    "/pedestal/position_target",
    "/leader/left_forward_position_controller/commands",
    "/leader/right_forward_position_controller/commands",
)


def generate_launch_description():
    launch_path = PathJoinSubstitution(
        [
            FindPackageShare("mobile_bimanual_bringup"),
            "launch",
            "robot.launch.py",
        ]
    )
    hardware_group = GroupAction(
        scoped=True,
        actions=[
            *[
                SetRemap(src=topic, dst="/hardware" + topic)
                for topic in COMMAND_TOPICS
            ],
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(launch_path),
                launch_arguments={
                    "use_fake_hardware": LaunchConfiguration(
                        "use_fake_hardware"
                    ),
                    "tracer_can_interface": LaunchConfiguration(
                        "tracer_can_interface"
                    ),
                }.items(),
            ),
        ],
    )
    return LaunchDescription(
        [
            DeclareLaunchArgument("use_fake_hardware", default_value="true"),
            DeclareLaunchArgument(
                "tracer_can_interface", default_value="can_tracer"
            ),
            # Gate is outside the scoped remaps: subscribes to PUBLIC names,
            # publishes to /hardware names, and owns the mode-selection service.
            Node(
                package="mobile_bimanual_control",
                executable="command_gate",
                output="screen",
            ),
            hardware_group,
        ]
    )
