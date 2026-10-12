from launch import LaunchDescription
from launch_ros.actions import Node
from launch.substitutions import (
    Command,
    FindExecutable,
    PathJoinSubstitution,
)
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    pedestal_openarm_xacro = PathJoinSubstitution(
        [
            FindPackageShare("mobile_bimanual_description"),
            "urdf",
            "pedestal_openarm.urdf.xacro",
        ]
    )

    rviz_config_path = PathJoinSubstitution(
        [
            FindPackageShare("mobile_bimanual_description"),
            "rviz",
            "pedestal_openarm.rviz",
        ],
    )

    pedestal_openarm_description_content = Command(
        [
            FindExecutable(name="xacro"),
            " ",
            pedestal_openarm_xacro,
        ]
    )

    robot_description_parameter = {
        "robot_description": ParameterValue(
            pedestal_openarm_description_content,
            value_type=str,
        )
    }

    robot_state_publisher_node = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        parameters=[
            robot_description_parameter,
        ],
        output="screen",
    )

    joint_state_publisher_gui = Node(
        package="joint_state_publisher_gui",
        executable="joint_state_publisher_gui",
        output="screen",
    )

    rviz_node = Node(
        package="rviz2",
        executable="rviz2",
        arguments=["-d", rviz_config_path],
    )

    return LaunchDescription(
        [
            robot_state_publisher_node,
            joint_state_publisher_gui,
            rviz_node,
        ]
    )
