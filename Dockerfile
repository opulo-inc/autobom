# Container image that runs your code
FROM ghcr.io/inti-cmnb/kicad8_auto

# apt update, install python, uv
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates

# Download the latest uv installer
ADD https://astral.sh/uv/install.sh /uv-installer.sh

# Run the installer then remove it
RUN sh /uv-installer.sh && rm /uv-installer.sh

# download and install freecad appimage
RUN curl -o FreeCAD.AppImage https://github.com/FreeCAD/FreeCAD/releases/download/0.21.2/FreeCAD-0.21.2-Linux-x86_64.AppImage \
    && sudo chown runner:docker FreeCAD.AppImage \
    && chmod +x FreeCAD.AppImage \
    && ./FreeCAD.AppImage --appimage-extract > /dev/null

# Copies your code file from your action repository to the filesystem path `/` of the container
COPY src /autobom



RUN 

WORKDIR /autobom

# Code file to execute when the docker container starts up (`entrypoint.sh`)
CMD ["uv", "run", "my_app"]


