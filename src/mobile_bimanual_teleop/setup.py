from setuptools import find_packages, setup

package_name = "mobile_bimanual_teleop"

setup(
    name=package_name,
    version="0.0.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        (
            "share/ament_index/resource_index/packages",
            ["resource/" + package_name],
        ),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools", "scipy", "mink", "mujoco"],
    zip_safe=True,
    maintainer="lukec",
    maintainer_email="43226681+Luke-kC@users.noreply.github.com",
    description="TODO: Package description",
    license="TODO: License declaration",
    extras_require={
        "test": [
            "pytest",
        ],
    },
    entry_points={
        "console_scripts": [
            "single_arm_teleop_node = mobile_bimanual_teleop.ros.single_arm_teleop_node:main",
        ],
    },
)
