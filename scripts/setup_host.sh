#!/usr/bin/env bash
set -euo pipefail

sudo apt update
sudo apt install -y \
    software-properties-common \
    jq \
    python3-vcstool \
    ros-dev-tools \
    ros-jazzy-ros2-control \
    ros-jazzy-ros2-controllers \
    ros-jazzy-foxglove-bridge \
    ros-jazzy-rosbag2-storage-mcap

if ! grep -Rqs '^deb .*ppa.launchpadcontent.net/openarm/main' /etc/apt/sources.list /etc/apt/sources.list.d 2>/dev/null; then
    sudo add-apt-repository -y ppa:openarm/main
    sudo apt update
fi

sudo apt install -y libopenarm-can-dev openarm-can-utils

echo "Host dependencies installed."
echo "Remember to source /opt/ros/jazzy/setup.zsh in zsh shells."
