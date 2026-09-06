FROM ros:jazzy-ros-base-noble

ARG USERNAME=ubuntu
ARG NEOVIM_VERSION=v0.12.2
ARG FZF_VERSION=0.74.3
ARG STARSHIP_VERSION=v1.26.0
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
    nix-bin \
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
    ros-jazzy-rqt-graph \
    can-utils \
    iproute2 \
    bat \
    eza \
    zoxide \
    ripgrep \
    fd-find \
    clangd \
    cmake-format \
    gdb \
    jq \
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
# Development user
# ---------------------------------------------------------------------------

RUN usermod --shell /usr/bin/zsh "${USERNAME}" \
    && echo "${USERNAME} ALL=(root) NOPASSWD:ALL" \
        > "/etc/sudoers.d/${USERNAME}" \
    && chmod 0440 "/etc/sudoers.d/${USERNAME}"

# Ubuntu calls fd "fdfind"; LazyVim/tools normally expect "fd".
RUN ln -s /usr/bin/fdfind /usr/local/bin/fd

# cmake-format installs the linter as "cmake-lint"; nvim-lint expects
# "cmakelint".
RUN ln -s /usr/bin/cmake-lint /usr/local/bin/cmakelint

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

# XML formatter used by the shared LazyVim config.
RUN npm install --global prettier @prettier/plugin-xml

# Shell tools required by the optional host ZDOTDIR configuration. The stock
# Noble fzf predates `fzf --zsh`, so install a current pinned release.
RUN ARCH="$(dpkg --print-architecture)" \
    && case "${ARCH}" in \
        amd64) FZF_ARCH="amd64"; STARSHIP_ARCH="x86_64" ;; \
        arm64) FZF_ARCH="arm64"; STARSHIP_ARCH="aarch64" ;; \
        *) echo "Unsupported architecture: ${ARCH}" && exit 1 ;; \
    esac \
    && FZF_ASSET="fzf-${FZF_VERSION}-linux_${FZF_ARCH}.tar.gz" \
    && curl -fsSL \
        "https://github.com/junegunn/fzf/releases/download/v${FZF_VERSION}/${FZF_ASSET}" \
        -o "/tmp/${FZF_ASSET}" \
    && curl -fsSL \
        "https://github.com/junegunn/fzf/releases/download/v${FZF_VERSION}/fzf_${FZF_VERSION}_checksums.txt" \
        -o /tmp/fzf-checksums.txt \
    && grep " ${FZF_ASSET}$" /tmp/fzf-checksums.txt | (cd /tmp && sha256sum -c -) \
    && tar -xzf "/tmp/${FZF_ASSET}" -C /usr/local/bin fzf \
    && STARSHIP_ASSET="starship-${STARSHIP_ARCH}-unknown-linux-musl.tar.gz" \
    && curl -fsSL \
        "https://github.com/starship/starship/releases/download/${STARSHIP_VERSION}/${STARSHIP_ASSET}" \
        -o "/tmp/${STARSHIP_ASSET}" \
    && curl -fsSL \
        "https://github.com/starship/starship/releases/download/${STARSHIP_VERSION}/${STARSHIP_ASSET}.sha256" \
        -o "/tmp/${STARSHIP_ASSET}.sha256" \
    && printf '%s  %s\n' "$(< "/tmp/${STARSHIP_ASSET}.sha256")" "${STARSHIP_ASSET}" \
        | (cd /tmp && sha256sum -c -) \
    && tar -xzf "/tmp/${STARSHIP_ASSET}" -C /usr/local/bin starship \
    && rm -f /tmp/fzf-checksums.txt "/tmp/${FZF_ASSET}" "/tmp/${STARSHIP_ASSET}" "/tmp/${STARSHIP_ASSET}.sha256"

# Named volumes mounted at these paths retain the development user's ownership.
RUN mkdir -p \
        "/home/${USERNAME}/.config" \
        "/home/${USERNAME}/.local/share/nvim" \
        "/home/${USERNAME}/.local/state/nvim" \
        "/home/${USERNAME}/.local/state/zsh" \
        "/home/${USERNAME}/.cache/nvim" \
        "/home/${USERNAME}/.cache/zsh" \
    && chown -R "${USERNAME}:${USERNAME}" \
        "/home/${USERNAME}/.config" \
        "/home/${USERNAME}/.local" \
        "/home/${USERNAME}/.cache"

# Mason builds some editor tools, including the Nix nil language server, from
# Rust sources. Ubuntu Noble's rustc is too old for nil, so use Rustup stable.
# nil also calls the `nix` command at build time; nix-bin provides it.
RUN curl -fsSL https://sh.rustup.rs -o /tmp/rustup-init.sh \
    && chmod +x /tmp/rustup-init.sh \
    && sudo -u "${USERNAME}" \
        HOME="/home/${USERNAME}" \
        CARGO_HOME="/home/${USERNAME}/.cargo" \
        RUSTUP_HOME="/home/${USERNAME}/.rustup" \
        /tmp/rustup-init.sh -y --profile minimal --default-toolchain stable \
    && rm /tmp/rustup-init.sh

# ---------------------------------------------------------------------------
# ROS shell setup
# ---------------------------------------------------------------------------

ENV ROS_WS=/workspace
ENV PATH="/home/${USERNAME}/.cargo/bin:/home/${USERNAME}/.local/bin:${PATH}"

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
