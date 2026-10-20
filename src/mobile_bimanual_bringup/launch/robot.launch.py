from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    use_fake_hardware = LaunchConfiguration("use_fake_hardware")

    tracer_can_interface_argument = DeclareLaunchArgument(
        "tracer_can_interface",
        default_value="can_tracer",
        description="SocketCAN interface for the Tracer.",
    )

    # Existing pedestal + OpenArm bringup
    pedestal_openarm_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [
                    FindPackageShare("mobile_bimanual_bringup"),
                    "launch",
                    "pedestal_openarm.launch.py",
                ]
            )
        ),
        launch_arguments={
            "use_fake_hardware": use_fake_hardware,
            "description_file": "mobile_bimanual.urdf.xacro",
        }.items(),
    )

    # AgileX Tracer bringup
    tracer_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [
                    FindPackageShare("tracer_base"),
                    "launch",
                    "tracer_base.launch.py",
                ]
            )
        ),
        launch_arguments={
            "port_name": LaunchConfiguration("tracer_can_interface"),
            "odom_frame": "odom",
            "base_frame": "base_link",
        }.items(),
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "use_fake_hardware",
                default_value="true",
                description="Use fake OpenArm hardware.",
            ),
            tracer_can_interface_argument,
            pedestal_openarm_launch,
            tracer_launch,
        ]
    )
