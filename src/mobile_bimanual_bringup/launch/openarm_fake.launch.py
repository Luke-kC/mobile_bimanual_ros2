from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    upstream_launch = PathJoinSubstitution(
        [
            FindPackageShare("openarm_bringup"),
            "launch",
            "openarm.bimanual.launch.py",
        ]
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "launch_rviz",
                default_value="false",
                description="Start RViz with the OpenArm configuration.",
            ),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(upstream_launch),
                launch_arguments={
                    "arm_type": "v1.0",
                    "use_fake_hardware": "true",
                    "robot_controller": "forward_position_controller",
                    "right_can_interface": "can0",
                    "left_can_interface": "can1",
                    "launch_rviz": LaunchConfiguration("launch_rviz"),
                }.items(),
            ),
        ]
    )
