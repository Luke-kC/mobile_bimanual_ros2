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

    description_file = PathJoinSubstitution(
        [
            FindPackageShare("mobile_bimanual_description"),
            "urdf",
            "openarm_v1_mujoco.ros2_control.xacro",
        ]
    )

    mujoco_model = PathJoinSubstitution(
        [
            FindPackageShare("mobile_bimanual_description"),
            "mujoco",
            "openarm_mujoco",
            "v1",
            "openarm_bimanual.xml",
        ]
    )

    controllers_file = PathJoinSubstitution(
        [
            FindPackageShare("mobile_bimanual_sim"),
            "config",
            "openarm_bimanual_controllers.yaml",
        ]
    )

    pids_file = PathJoinSubstitution(
        [
            FindPackageShare("mobile_bimanual_sim"),
            "config",
            "openarm_pids.yaml",
        ]
    )

    robot_description_content = Command(
        [
            FindExecutable(name="xacro"),
            " ",
            description_file,
            " mujoco_model:=",
            mujoco_model,
            " pids_config_file:=",
            pids_file,
            " headless:=",
            headless,
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
            Node(
                package="tf2_ros",
                executable="static_transform_publisher",
                arguments=[
                    "--x",
                    "0",
                    "--y",
                    "0",
                    "--z",
                    "0",
                    "--roll",
                    "0",
                    "--pitch",
                    "0",
                    "--yaw",
                    "0",
                    "--frame-id",
                    "world",
                    "--child-frame-id",
                    "sim/world",
                ],
                output="screen",
            ),
            Node(
                package="robot_state_publisher",
                executable="robot_state_publisher",
                parameters=[
                    robot_description,
                    {
                        "use_sim_time": True,
                        "frame_prefix": "sim/",
                    },
                ],
                namespace="sim",
                output="screen",
            ),
            Node(
                package="mujoco_ros2_control",
                executable="ros2_control_node",
                parameters=[
                    {"use_sim_time": True},
                    controllers_file,
                ],
                namespace="sim",
                output="screen",
            ),
            Node(
                package="controller_manager",
                executable="spawner",
                arguments=[
                    "joint_state_broadcaster",
                    "left_arm_position_controller",
                    "right_arm_position_controller",
                    "--param-file",
                    controllers_file,
                ],
                namespace="sim",
                output="screen",
            ),
        ]
    )
