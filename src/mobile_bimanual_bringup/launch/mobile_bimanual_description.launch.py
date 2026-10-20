from launch import LaunchDescription, condition
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import (
    Command,
    FindExecutable,
    LaunchConfiguration,
    PathJoinSubstitution,
)
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():

    use_gui_argument = DeclareLaunchArgument(
        "use_gui",
        default_value="true",
        description="Enable manual joint-state GUI for model testing.",
    )

    joint_states_topic_argument = DeclareLaunchArgument(
        "joint_states_topic",
        default_value="/joint_states",
        description="Sets the topic that robot_state_publisher subscribes to.",
    )

    pedestal_openarm_xacro = PathJoinSubstitution(
        [
            FindPackageShare("mobile_bimanual_description"),
            "urdf",
            "mobile_bimanual.urdf.xacro",
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
        remappings=[
            ("/joint_states", LaunchConfiguration("joint_states_topic")),
        ],
        output="screen",
    )

    joint_state_publisher_gui = Node(
        package="joint_state_publisher_gui",
        executable="joint_state_publisher_gui",
        output="screen",
        condition=IfCondition(LaunchConfiguration("use_gui")),
    )

    rviz_node = Node(
        package="rviz2",
        executable="rviz2",
        arguments=["-d", rviz_config_path],
    )

    return LaunchDescription(
        [
            use_gui_argument,
            joint_states_topic_argument,
            robot_state_publisher_node,
            joint_state_publisher_gui,
            rviz_node,
        ]
    )
