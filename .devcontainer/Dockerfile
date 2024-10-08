FROM mcr.microsoft.com/devcontainers/python:3.12-bookworm

RUN apt update && apt upgrade -y

RUN apt install -y \
    direnv \
    pipx

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
