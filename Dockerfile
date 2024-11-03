# Container image that runs your code
FROM ghcr.io/inti-cmnb/kicad8_auto
#FROM ubuntu:24.04

# apt update, install python, uv
RUN apt-get update \
    && apt remove -y libcurl4

RUN apt-get install -y wget ca-certificates libfuse2 sudo

# ---------------
# FREECAD INSTALL
# ---------------

# installing python and such
RUN apt update \
    && apt-get -y install python3 \
    && apt-get -y install python3-pip \
    && apt-get -y install qtbase5-dev

# download and install freecad appimage
RUN wget https://github.com/FreeCAD/FreeCAD/releases/download/0.21.2/FreeCAD-0.21.2-Linux-aarch64.AppImage -O /FreeCAD.AppImage

# change permissions of appimage
RUN chmod +x /FreeCAD.AppImage

# extract the guts of the appimage
RUN ./FreeCAD.AppImage --appimage-extract > /dev/null

# ---------------
# UV INSTALL
# ---------------

# Download the latest uv installer
ADD https://astral.sh/uv/install.sh /uv-installer.sh

# Run the installer then remove it
RUN sudo chmod a+x /uv-installer.sh && ./uv-installer.sh && rm /uv-installer.sh

# Add to path
ENV PATH="/root/.cargo/bin/:$PATH"

# ---------------
# Directory Setup
# ---------------

# Copies your code file from your action repository to the filesystem path `/` of the container
COPY . /autobom

# remove existing virtual environment
RUN sudo rm -r /autobom/.venv

WORKDIR /autobom/example

RUN uv sync --verbose

# Code file to execute when the docker container starts up (`entrypoint.sh`)
#CMD ["uv", "run", "autobom"]

CMD ["echo", "'out=success'", ">>", "$GITHUB_OUTPUT"] 

# setting up a non-root user

# RUN adduser \
#     --system \
#     --shell /bin/bash \
#     --group \
#     --disabled-password \
#     --home /home/autobom \
#     autobom \
#     && passwd -d autobom

# RUN usermod -a -G sudo autobom

#USER autobom