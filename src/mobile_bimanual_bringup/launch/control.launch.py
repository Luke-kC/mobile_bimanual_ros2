from launch import LaunchDescription
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description() -> LaunchDescription:
    control_config = PathJoinSubstitution(
        [
            FindPackageShare("mobile_bimanual_control"),
            "config",
            "control.yaml",
        ]
    )

    supervisor_node = Node(
        package="mobile_bimanual_control",
        executable="supervisor",
        name="supervisor",
        output="screen",
    )

    command_bridge_node = Node(
        package="mobile_bimanual_control",
        executable="command_bridge",
        name="command_bridge",
        output="screen",
        parameters=[control_config],
    )

    return LaunchDescription(
        [
            supervisor_node,
            command_bridge_node,
        ]
    )
