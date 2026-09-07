from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    LaunchConfiguration,
    NotSubstitution,
    PathJoinSubstitution,
)
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    sim_leader_launch_path = PathJoinSubstitution(
        [
            FindPackageShare("openarm_bringup"),
            "launch",
            "openarm.bimanual.launch.py",
        ]
    )

    sim_leader_launch_description = IncludeLaunchDescription(
        launch_description_source=PythonLaunchDescriptionSource(
            sim_leader_launch_path
        ),
        launch_arguments={
            "arm_type": "v1.0",
            "use_fake_hardware": "true",
            "robot_controller": "forward_position_controller",
            "right_can_interface": "can0",
            "left_can_interface": "can1",
            "arm_prefix": "leader",
            "runtime_config_package": "mobile_bimanual_bringup",
            "controllers_file": "openarm_leader_controllers.yaml",
            "launch_rviz": NotSubstitution(LaunchConfiguration("headless")),
        }.items(),
    )

    sim_follower_launch_path = PathJoinSubstitution(
        [
            FindPackageShare("mobile_bimanual_sim"),
            "launch",
            "yam_single.launch.py",
        ]
    )

    sim_follower_launch_description = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(sim_follower_launch_path),
        launch_arguments={
            "headless": LaunchConfiguration("headless"),
            "scene": LaunchConfiguration("scene"),
            "initial_keyframe": LaunchConfiguration("initial_keyframe"),
        }.items(),
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
            DeclareLaunchArgument(
                "scene",
                default_value="yam_empty.xml",
                description="MuJoCo scene file to load for the YAM sim.",
            ),
            DeclareLaunchArgument(
                "initial_keyframe",
                default_value="",
                description="MuJoCo keyframe used for YAM initial simulation state.",
            ),
            sim_leader_launch_description,
            sim_follower_launch_description,
            foxglove_launch_description,
        ]
    )
