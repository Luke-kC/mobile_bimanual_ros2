from launch import LaunchDescription
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch.substitutions import PathJoinSubstitution


def generate_launch_description() -> LaunchDescription:
    control_config = PathJoinSubstitution(
        [
            FindPackageShare("mobile_bimanual_control"),
            "config",
            "control.yaml",
        ]
    )

    return LaunchDescription(
        [
            Node(
                package="mobile_bimanual_control",
                executable="command_bridge",
                name="command_bridge",
                output="screen",
                parameters=[control_config],
            ),
        ]
    )
