from launch import LaunchDescription
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description() -> LaunchDescription:

    port_argument = DeclareLaunchArgument(
        name="port",
        default_value="/dev/pedestal",
        description="Serial port for the pedestal MCU",
    )

    publish_rate_hz_argument = DeclareLaunchArgument(
        name="publish_rate_hz",
        default_value="20.0",
        description="ROS telemetry publication frequency for the pedestal",
    )

    joint_name_argument = DeclareLaunchArgument(
        name="joint_name",
        default_value="pedestal_joint",
        description="Joint name; must match the unified robot URDF",
    )

    telem_timeout_s_argument = DeclareLaunchArgument(
        name="telem_timeout_s",
        default_value="0.3",
        description="Telemetry freshness timeout",
    )

    position_filter_tau_s_argument = DeclareLaunchArgument(
        name="position_filter_tau_s",
        default_value="0.25",
        description="Position low pass filter time constant",
    )

    pedestal_node = Node(
        package="mobile_bimanual_hardware",
        executable="pedestal_node",
        name="pedestal_node",
        parameters=[
            {
                "port": LaunchConfiguration("port"),
                "publish_rate_hz": ParameterValue(
                    LaunchConfiguration("publish_rate_hz"), value_type=float
                ),
                "joint_name": LaunchConfiguration("joint_name"),
                "telem_timeout_s": ParameterValue(
                    LaunchConfiguration("telem_timeout_s"), value_type=float
                ),
                "position_filter_tau_s": ParameterValue(
                    LaunchConfiguration("position_filter_tau_s"),
                    value_type=float,
                ),
            }
        ],
        output="screen",
    )

    return LaunchDescription(
        [
            port_argument,
            publish_rate_hz_argument,
            joint_name_argument,
            telem_timeout_s_argument,
            position_filter_tau_s_argument,
            pedestal_node,
        ]
    )
