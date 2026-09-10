import os
from glob import glob

from setuptools import find_packages, setup

package_name = "mobile_bimanual_bringup"

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
        ("share/" + package_name + "/launch", glob("launch/*.launch.py")),
        (
            os.path.join("share", package_name, "config", "controllers"),
            glob("config/controllers/*.yaml"),
        ),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Lab Maintainer",
    maintainer_email="maintainer@example.com",
    description="Bringup and observability for a mobile bimanual robot.",
    license="Apache-2.0",
)
