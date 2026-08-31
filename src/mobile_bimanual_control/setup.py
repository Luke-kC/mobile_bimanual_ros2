import os
from glob import glob
from setuptools import find_packages, setup

package_name = "mobile_bimanual_control"

setup(
    name=package_name,
    version="0.0.1",
    packages=find_packages(),
    data_files=[
        (
            "share/ament_index/resource_index/packages",
            ["resource/" + package_name],
        ),
        ("share/" + package_name, ["package.xml"]),
        (
            os.path.join("share", package_name, "config"),
            glob("config/*.yaml"),
        ),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Lab Maintainer",
    maintainer_email="maintainer@example.com",
    description="Python command and safety nodes for a mobile bimanual robot.",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "joint_state_watch = mobile_bimanual_control.ros.joint_state_watch_node:main",
            "command_bridge = mobile_bimanual_control.ros.command_bridge_node:main",
        ],
    },
)
