from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription(
        [
            Node(
                package="foxglove_bridge",
                executable="foxglove_bridge",
                name="foxglove_bridge",
                output="screen",
                parameters=[
                    {
                        "asset_uri_allowlist": [
                            (
                                r"^package://(?:openarm_description|mobile_bimanual_description)/"
                                r"(?:[-\w%.]+/)*"
                                r"[-\w%.]+\."
                                r"(?:dae|fbx|glb|gltf|jpeg|jpg|mtl|"
                                r"obj|png|stl|tif|tiff|urdf|webp|xacro)$"
                            )
                        ]
                    }
                ],
            ),
        ]
    )
