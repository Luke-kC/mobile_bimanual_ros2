from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import (
    Command,
    FindExecutable,
    LaunchConfiguration,
    PathJoinSubstitution,
)
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description() -> LaunchDescription:
    headless = LaunchConfiguration("headless")
    scene = LaunchConfiguration("scene")
    initial_keyframe = LaunchConfiguration("initial_keyframe")

    description_file = PathJoinSubstitution(
        [
            FindPackageShare("mobile_bimanual_description"),
            "urdf",
            "yam_v1.ros2_control.xacro",
        ]
    )

    mujoco_model = PathJoinSubstitution(
        [
            FindPackageShare("mobile_bimanual_description"),
            "mujoco",
            "yam_v1",
            scene,
        ]
    )

    controllers_file = PathJoinSubstitution(
        [
            FindPackageShare("mobile_bimanual_sim"),
            "config",
            "yam_single_controllers.yaml",
        ]
    )

    robot_description_content = Command(
        [
            FindExecutable(name="xacro"),
            " ",
            description_file,
            " mujoco_model:=",
            mujoco_model,
            " headless:=",
            headless,
            " initial_keyframe:=",
            initial_keyframe,
        ]
    )

    robot_description = {
        "robot_description": ParameterValue(
            robot_description_content,
            value_type=str,
        )
    }

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "headless",
                default_value="false",
            ),
            DeclareLaunchArgument(
                "scene",
                default_value="yam_empty.xml",
                description="MuJoCo scene file to load.",
            ),
            DeclareLaunchArgument(
                "initial_keyframe",
                default_value="",
                description="MuJoCo keyframe used for initial simulation state.",
            ),
            Node(
                package="robot_state_publisher",
                executable="robot_state_publisher",
                parameters=[
                    robot_description,
                    {"use_sim_time": True},
                ],
                namespace="follower",
                output="screen",
            ),
            Node(
                package="mujoco_ros2_control",
                executable="ros2_control_node",
                parameters=[
                    {"use_sim_time": True},
                    controllers_file,
                ],
                namespace="follower",
                output="screen",
            ),
            Node(
                package="controller_manager",
                executable="spawner",
                arguments=[
                    "joint_state_broadcaster",
                    "yam_position_controller",
                    "--param-file",
                    controllers_file,
                ],
                namespace="follower",
                output="screen",
            ),
        ]
    )
