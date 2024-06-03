# Container image that runs your code
FROM alpine:3.14

# Copies your code file from your action repository to the filesystem path `/` of the container
COPY src /autobom

RUN apt-get update && apt-get install -y \
    python3 \

WORKDIR /autobom

# Code file to execute when the docker container starts up (`entrypoint.sh`)
RUN ["chmod", "+x", "/autobom/entrypoint.sh"]
ENTRYPOINT ["/autobom/entrypoint.sh"]


