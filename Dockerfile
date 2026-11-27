FROM ghcr.io/astral-sh/uv:0.13.10 AS uv

# Sync NVIDIA Driver & CUDA versions (`nvidia-smi`)
FROM nvidia/cuda:13.5.0-devel-ubuntu24.04

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get -yq update && \
    apt-get -yq remove python && \
    apt-get -yyq install \
        -o APT::Install-Recommends=false \
        -o APT::Install-Suggests=false \
        build-essential \
        cmake \
        curl \
        fzf \
        git \
        git-lfs \
        libasound2-plugins \
        libnvidia-compute-595-server \
        ncurses-bin \
        openssh-client \
        pipewire-bin \
        npm \
        ripgrep \
        sudo && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
# build-essential - N/A
# cmake - lightgbm (older, non-wheel version)
# curl - Claude Code
# fzf - N/A
# git - N/A
# git-lfs - N/A
# libasound2-plugins - Claude Code voice (ALSA to PulseAudio routing)
# libnvidia-compute-595-server - lightgbm
# ncurses-bin - Claude Code
# openssh-client - git push over SSH
# pipewire-bin - Claude Code
# npm - MCP (provides node, npx)
# ripgrep - Claude Code

COPY --from=uv /uv /uvx /bin/
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_HTTP_TIMEOUT=60 \
    UV_NO_CACHE=1 \
    UV_PYTHON=python3.13 \
    UV_PYTHON_INSTALL_DIR=/app/python \
    VIRTUAL_ENV=/app/venv
# Initiate Virtual Environment
RUN /bin/uv venv $VIRTUAL_ENV

ENV USER=user
ENV HOME=/home/$USER
RUN userdel -r ubuntu 2> /dev/null || true
RUN getent group 1000 > /dev/null 2>&1 || groupadd -g 1000 user
RUN useradd -m -s /bin/bash -u 1000 -g 1000 $USER && \
    chown -R $USER:$USER $HOME /app && \
    echo "$USER ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers
USER $USER

ENV TERM=xterm-256color
# Route ALSA default device through PulseAudio (Claude Code voice mode)
RUN /bin/bash -c "echo -e 'pcm.!default pulse\nctl.!default pulse' > $HOME/.asoundrc"

RUN (curl --proto '=https' --tlsv1.2 -fsSL https://claude.ai/install.sh | /bin/bash) && \
    (curl --proto '=https' --tlsv1.2 -fsSL https://opencode.ai/install | /bin/bash)
ARG LLAMA_RELEASE=prism-b12232-f702476
ARG LLAMA_CUDA=13.3
ARG LLAMA_SHA256=69db0170344c7d57e0f60c1431bc6c36abd43ae81e032be013787b5e450ad472
RUN curl --proto '=https' --tlsv1.2 -fsSL -o /tmp/llama.tar.gz \
        https://github.com/PrismML-Eng/llama.cpp/releases/download/$LLAMA_RELEASE/llama-$LLAMA_RELEASE-bin-linux-cuda-$LLAMA_CUDA-x64.tar.gz && \
    echo "$LLAMA_SHA256  /tmp/llama.tar.gz" | sha256sum -c - && \
    mkdir -p $HOME/.local/lib/llama $HOME/.local/bin && \
    tar -xzf /tmp/llama.tar.gz -C $HOME/.local/lib/llama --strip-components=1 && \
    ln -s $HOME/.local/lib/llama/llama $HOME/.local/bin/llama && \
    rm /tmp/llama.tar.gz
ENV PATH="$PATH:$VIRTUAL_ENV/bin:$HOME/.local/bin:$HOME/.opencode/bin"

RUN --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    /bin/uv sync --active --frozen --extra dev --no-install-project
COPY --chown=$USER:$USER . /app/shrubbery
RUN /bin/uv pip install --python $VIRTUAL_ENV --no-deps /app/shrubbery && \
    rm -rf /app/shrubbery
ENTRYPOINT ["/bin/bash"]
