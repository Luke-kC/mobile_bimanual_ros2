from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    IncludeLaunchDescription,
    LogInfo,
    TimerAction,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    LaunchConfiguration,
    NotSubstitution,
    PathJoinSubstitution,
    PythonExpression,
)
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    hardware_leader_launch_path = PathJoinSubstitution(
        [
            FindPackageShare("openarm_bringup"),
            "launch",
            "openarm.bimanual.launch.py",
        ]
    )

    hardware_leader_launch_description = IncludeLaunchDescription(
        launch_description_source=PythonLaunchDescriptionSource(
            hardware_leader_launch_path
        ),
        launch_arguments={
            "arm_type": "v1.0",
            "use_fake_hardware": "false",
            "robot_controller": "forward_position_controller",
            "right_can_interface": "can0",
            "left_can_interface": "can1",
            "arm_prefix": "leader",
            "runtime_config_package": "mobile_bimanual_bringup",
            "controllers_file": "openarm_leader_controllers.yaml",
            "launch_rviz": NotSubstitution(LaunchConfiguration("headless")),
        }.items(),
    )

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

    foxglove_launch_path = PathJoinSubstitution(
        [
            FindPackageShare("mobile_bimanual_bringup"),
            "launch",
            "observability.launch.py",
        ]
    )

    foxglove_launch_description = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(foxglove_launch_path),
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "headless",
                default_value="false",
                description="Set true to start without RViz for OpenArm and without MuJoCo GUI for YAM.",
            ),
            hardware_leader_launch_description,
            supervisor_node,
            command_bridge_node,
            foxglove_launch_description,
        ]
    )
