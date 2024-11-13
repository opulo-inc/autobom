# Copyright (c) 2024 Opulo, Inc
# Published under the Mozilla Public License
# Full text available at: https://www.mozilla.org/en-US/MPL/

# BUILD:
#   docker build -t autobom .

# RUN:
#   docker run -it --rm autobom

FROM ubuntu:24.04

# SHELL ["/bin/bash", "-c"]

RUN apt update && \
    apt-get -y install software-properties-common wget && \
    apt update

# ---------------
# UV INSTALL
# ---------------

# download and run uv installer
ADD --chmod=755 https://astral.sh/uv/install.sh /install.sh
RUN /install.sh && rm /install.sh

# Add uv to path
ENV PATH="/root/.local/bin/:$PATH"

# ---------------
# Directory Setup
# ---------------

# # Copies your code file from your action repository to the filesystem path `/` of the container
COPY . /autobom

# Clone repo into /data/autobom
RUN git clone git://github.com/opulo-inc/paste-extruder.git repo

WORKDIR /autobom/repo

# Code file to execute when the docker container starts up (`entrypoint.sh`)
CMD ["uv", "run", "autobom"]

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