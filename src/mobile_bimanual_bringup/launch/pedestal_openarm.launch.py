from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    GroupAction,
    IncludeLaunchDescription,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    Command,
    FindExecutable,
    LaunchConfiguration,
    PathJoinSubstitution,
)
from launch_ros.actions import Node, SetRemap
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_pedestal_launch_description():
    port_argument = DeclareLaunchArgument("port", default_value="/dev/pedestal")
    publish_rate_hz_argument = DeclareLaunchArgument(
        "publish_rate_hz",
        default_value="20.0",
    )
    joint_name_argument = DeclareLaunchArgument(
        "joint_name",
        default_value="pedestal_joint",
    )
    telem_timeout_s_argument = DeclareLaunchArgument(
        "telem_timeout_s",
        default_value="0.3",
    )
    position_filter_tau_s_argument = DeclareLaunchArgument(
        "position_filter_tau_s",
        default_value="0.25",
    )

    pedestal_launch_path = PathJoinSubstitution(
        [
            FindPackageShare("mobile_bimanual_bringup"),
            "launch",
            "pedestal.launch.py",
        ]
    )

    pedestal_launch_arguments = {
        "port": LaunchConfiguration("port"),
        "publish_rate_hz": LaunchConfiguration("publish_rate_hz"),
        "joint_name": LaunchConfiguration("joint_name"),
        "telem_timeout_s": LaunchConfiguration("telem_timeout_s"),
        "position_filter_tau_s": LaunchConfiguration("position_filter_tau_s"),
    }

    pedestal_launch_description = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(pedestal_launch_path),
        launch_arguments=pedestal_launch_arguments.items(),
    )

    return [
        port_argument,
        publish_rate_hz_argument,
        joint_name_argument,
        telem_timeout_s_argument,
        position_filter_tau_s_argument,
        pedestal_launch_description,
    ]


def generate_launch_description():
    use_fake_hardware_argument = DeclareLaunchArgument(
        "use_fake_hardware",
        default_value="true",
        description="Use fake OpenArm hardware.",
    )

    description_file_argument = DeclareLaunchArgument(
        "description_file",
        default_value="pedestal_openarm.urdf.xacro",
        description="Robot description Xacro filename.",
    )

    openarm_launch_path = PathJoinSubstitution(
        [
            FindPackageShare("openarm_bringup"),
            "launch",
            "openarm.bimanual.launch.py",
        ]
    )

    openarm_launch_description = IncludeLaunchDescription(
        launch_description_source=PythonLaunchDescriptionSource(
            openarm_launch_path,
        ),
        launch_arguments={
            "arm_type": "v1.0",
            "use_fake_hardware": LaunchConfiguration("use_fake_hardware"),
            "robot_controller": "forward_position_controller",
            "right_can_interface": "can_arm_r",
            "left_can_interface": "can_arm_l",
            "arm_prefix": "leader",
            "runtime_config_package": "mobile_bimanual_bringup",
            "controllers_file": "openarm_leader_controllers.yaml",
            "launch_rviz": "false",
            "launch_rsp": "false",
        }.items(),
    )

    openarm_group = GroupAction(
        scoped=True,
        actions=[
            SetRemap(src="/leader/robot_description", dst="/robot_description"),
            SetRemap(src="/tf", dst="/leader/tf"),
            SetRemap(src="/tf_static", dst="/leader/tf_static"),
            openarm_launch_description,
        ],
    )

    openarm_joint_state_relay = Node(
        package="topic_tools",
        executable="relay",
        name="openarm_joint_state_relay",
        parameters=[
            {
                "input_topic": "/leader/joint_states",
                "output_topic": "/joint_states",
            }
        ],
        output="screen",
    )

    pedestal_launch_description = generate_pedestal_launch_description()

    pedestal_joint_state_relay = Node(
        package="topic_tools",
        executable="relay",
        name="pedestal_joint_state_relay",
        parameters=[
            {
                "input_topic": "/pedestal/joint_states",
                "output_topic": "/joint_states",
            }
        ],
        output="screen",
    )

    robot_xacro = PathJoinSubstitution(
        [
            FindPackageShare("mobile_bimanual_description"),
            "urdf",
            LaunchConfiguration("description_file"),
        ]
    )

    robot_description_content = Command(
        [
            FindExecutable(name="xacro"),
            " ",
            robot_xacro,
            " ros2_control:=true",
            " use_fake_hardware:=",
            LaunchConfiguration("use_fake_hardware"),
            " left_can_interface:=can_arm_l",
            " right_can_interface:=can_arm_r",
            " can_fd:=false",
        ]
    )

    robot_description_parameter = {
        "robot_description": ParameterValue(
            robot_description_content,
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

    rviz_config_path = PathJoinSubstitution(
        [
            FindPackageShare("mobile_bimanual_description"),
            "rviz",
            "pedestal_openarm.rviz",
        ],
    )

    rviz_node = Node(
        package="rviz2",
        executable="rviz2",
        arguments=["-d", rviz_config_path],
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
            use_fake_hardware_argument,
            description_file_argument,
            openarm_group,
            *pedestal_launch_description,
            openarm_joint_state_relay,
            pedestal_joint_state_relay,
            robot_state_publisher_node,
            rviz_node,
            foxglove_launch_description,
        ]
    )
