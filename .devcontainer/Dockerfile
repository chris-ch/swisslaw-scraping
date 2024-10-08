FROM mcr.microsoft.com/devcontainers/python:3.12-bookworm

RUN apt update && apt upgrade -y

RUN apt install -y \
    direnv \
    pipx \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libx11-xcb1 \
    libgtk-3-0 \
    libxcursor1 \
    libgdk-pixbuf2.0-0 \
    libpangocairo-1.0-0 \
    libcairo-gobject2 \
    libatk-bridge2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libatspi2.0-0 \
    libnspr4 \
    libnss3 \
    libasound2 \
    libgstreamer1.0-0 \
    libgstreamer-plugins-base1.0-0 \
    libgstreamer-plugins-good1.0-0 \
    libwoff1 \
    libvpx7 \
    libopus0 \
    libharfbuzz-icu0 \
    libenchant-2-2 \
    libsecret-1-0 \
    libhyphen0 \
    libmanette-0.2-0 \
    libflite1 \
    libflite1-dev \
    libgles2-mesa \
    libx264-160

ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID

# Ensure user exists and has correct UID/GID
RUN if ! id -u $USERNAME > /dev/null 2>&1; then \
        groupadd --gid $USER_GID $USERNAME \
        && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME; \
    else \
        usermod -u $USER_UID $USERNAME \
        && groupmod -g $USER_GID $(id -gn $USERNAME); \
    fi

# Create and set permissions for .vscode-server directories
RUN mkdir -p /home/$USERNAME/.vscode-server /home/$USERNAME/.vscode-server-insiders \
    && chown -R $USERNAME:$USER_GID /home/$USERNAME

# Switch to non-root user
USER $USERNAME

RUN pipx ensurepath
RUN pipx install poetry

# Set the working directory to the user's home
WORKDIR /home/$USERNAME
