from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare
from launch_ros.actions import Node


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
    tracer_launch = Node(
        package="tracer_base",
        executable="tracer_base_node",
        output="screen",
        parameters=[{
            "port_name": LaunchConfiguration("tracer_can_interface"),
            # Foxglove may discover all TFMessage topics, including raw_tf.
            # Keep raw frames disconnected from the filtered robot TF tree.
            "odom_frame": "tracer_raw_odom",
            "base_frame": "tracer_raw_base_link",
            "odom_topic_name": "/odom/raw",
        }],
        remappings=[("/tf", "/tracer/raw_tf")],
    )
    filtered_odometry = Node(
        package="mobile_bimanual_bringup",
        executable="filtered_odometry",
        output="screen",
        parameters=[PathJoinSubstitution([
            FindPackageShare("mobile_bimanual_bringup"), "config", "odometry_filter.yaml",
        ])],
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
            filtered_odometry,
        ]
    )
