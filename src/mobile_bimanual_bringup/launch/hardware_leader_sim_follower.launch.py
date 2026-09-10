from launch import LaunchDescription
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

    sim_follower_launch_path = PathJoinSubstitution(
        [
            FindPackageShare("mobile_bimanual_sim"),
            "launch",
            "openarm_bimanual.launch.py",
        ]
    )

    sim_follower_launch_description = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(sim_follower_launch_path),
        launch_arguments={
            "headless": LaunchConfiguration("headless"),
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

    deactivate_controllers_action = TimerAction(
        period=LaunchConfiguration("leader_disable_delay"),
        actions=[
            LogInfo(
                msg="Disabling leader controllers before disabling motors..."
            ),
            ExecuteProcess(
                cmd=[
                    "ros2",
                    "control",
                    "switch_controllers",
                    "--controller-manager",
                    "/leader/controller_manager",
                    "--deactivate",
                    "left_forward_position_controller",
                    "right_forward_position_controller",
                    "left_gripper_controller",
                    "right_gripper_controller",
                ],
                output="screen",
            ),
        ],
    )

    deactivate_hardware_action = TimerAction(
        period=PythonExpression(
            [LaunchConfiguration("leader_disable_delay"), " + 1.0"]
        ),
        actions=[
            LogInfo(msg="Disabling leader hardware components/motors..."),
            ExecuteProcess(
                cmd=[
                    "ros2",
                    "control",
                    "set_hardware_component_state",
                    "--controller-manager",
                    "/leader/controller_manager",
                    "openarm_left_hardware_interface",
                    "inactive",
                ],
                output="screen",
            ),
            ExecuteProcess(
                cmd=[
                    "ros2",
                    "control",
                    "set_hardware_component_state",
                    "--controller-manager",
                    "/leader/controller_manager",
                    "openarm_right_hardware_interface",
                    "inactive",
                ],
                output="screen",
            ),
            LogInfo(msg="Leader motor disable commands sent."),
        ],
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "headless",
                default_value="false",
                description="Set true to start without RViz for OpenArm and without MuJoCo GUI for YAM.",
            ),
            # DeclareLaunchArgument(
            #     "scene",
            #     default_value="yam_empty.xml",
            #     description="MuJoCo scene file to load for the YAM sim.",
            # ),
            # DeclareLaunchArgument(
            #     "initial_keyframe",
            #     default_value="",
            #     description="MuJoCo keyframe used for YAM initial simulation state.",
            # ),
            DeclareLaunchArgument(
                "leader_disable_delay",
                default_value="6.0",
                description="Time delay [seconds] from launch to disable leader arm controllers and motors",
            ),
            hardware_leader_launch_description,
            deactivate_controllers_action,
            deactivate_hardware_action,
            sim_follower_launch_description,
            foxglove_launch_description,
        ]
    )
