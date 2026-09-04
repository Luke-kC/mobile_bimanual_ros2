FROM ros:jazzy-ros-base-noble

ARG USERNAME=rosdev
ARG USER_UID=1000
ARG USER_GID=1000
ARG NEOVIM_VERSION=v0.12.2
ARG DEBIAN_FRONTEND=noninteractive

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# ---------------------------------------------------------------------------
# General development + ROS dependencies
# ---------------------------------------------------------------------------

RUN apt-get update && apt-get install -y --no-install-recommends \
    sudo \
    zsh \
    curl \
    ca-certificates \
    git \
    git-lfs \
    software-properties-common \
    build-essential \
    cmake \
    ninja-build \
    pkg-config \
    python3-dev \
    python3-pip \
    python3-venv \
    python3-vcstool \
    ros-dev-tools \
    ros-jazzy-ros2-control \
    ros-jazzy-ros2-controllers \
    ros-jazzy-foxglove-bridge \
    ros-jazzy-rosbag2-storage-mcap \
    ros-jazzy-mujoco-ros2-control \
    ros-jazzy-mujoco-ros2-control-demos \
    ros-jazzy-tf2-tools \
    can-utils \
    iproute2 \
    ripgrep \
    fd-find \
    clangd \
    nodejs \
    npm \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# OpenArm CAN dependency
# ---------------------------------------------------------------------------

RUN add-apt-repository -y ppa:openarm/main \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        libopenarm-can-dev \
        openarm-can-utils \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Non-root development user
# ---------------------------------------------------------------------------

RUN groupadd --gid "${USER_GID}" "${USERNAME}" \
    && useradd \
        --uid "${USER_UID}" \
        --gid "${USER_GID}" \
        --create-home \
        --shell /usr/bin/zsh \
        "${USERNAME}" \
    && echo "${USERNAME} ALL=(root) NOPASSWD:ALL" \
        > "/etc/sudoers.d/${USERNAME}" \
    && chmod 0440 "/etc/sudoers.d/${USERNAME}"

# Ubuntu calls fd "fdfind"; LazyVim/tools normally expect "fd".
RUN ln -s /usr/bin/fdfind /usr/local/bin/fd

# ---------------------------------------------------------------------------
# Neovim
# ---------------------------------------------------------------------------

RUN ARCH="$(dpkg --print-architecture)" \
    && case "${ARCH}" in \
        amd64) NVIM_ARCH="x86_64" ;; \
        arm64) NVIM_ARCH="arm64" ;; \
        *) echo "Unsupported architecture: ${ARCH}" && exit 1 ;; \
    esac \
    && curl -fsSL \
       "https://github.com/neovim/neovim/releases/download/${NEOVIM_VERSION}/nvim-linux-${NVIM_ARCH}.tar.gz" \
       -o /tmp/nvim.tar.gz \
    && mkdir -p /opt/nvim \
    && tar \
       -xzf /tmp/nvim.tar.gz \
       -C /opt/nvim \
       --strip-components=1 \
    && ln -s /opt/nvim/bin/nvim /usr/local/bin/nvim \
    && rm /tmp/nvim.tar.gz

# LazyVim prerequisite.
RUN npm install --global tree-sitter-cli

# ---------------------------------------------------------------------------
# ROS shell setup
# ---------------------------------------------------------------------------

ENV ROS_WS=/workspace
ENV PATH="/home/${USERNAME}/.local/bin:${PATH}"

RUN cat <<'EOF' >> /etc/zsh/zshrc

# ROS 2 Jazzy
source /opt/ros/jazzy/setup.zsh

# Source the local workspace after it has been built.
if [[ -f "${ROS_WS}/install/setup.zsh" ]]; then
    source "${ROS_WS}/install/setup.zsh"
fi
EOF

USER ${USERNAME}

WORKDIR /workspace
