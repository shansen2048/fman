FROM ubuntu:14.04

RUN apt-get update && \
    apt-get upgrade -y

RUN DEBIAN_FRONTEND=noninteractive apt-get install software-properties-common -y && \
    add-apt-repository ppa:deadsnakes/ppa -y && \
    apt-get update && \
    apt-get install python3.5 python3.5-dev python3.5-venv -y

WORKDIR /tmp

ADD id_rsa /root/.ssh/id_rsa
RUN chmod 600 /root/.ssh/id_rsa
ADD id_rsa.pub /root/.ssh/id_rsa.pub
RUN apt-get install openssh-client -y && \
    ssh-keyscan -H dev.herrmann.io >> ~/.ssh/known_hosts && \
    ssh-keyscan -H fman.io >> ~/.ssh/known_hosts && \
    chmod 600 ~/.ssh/known_hosts

RUN apt-get install git -y && \
    git config --global user.email "michael@herrmann.io" && \
    git config --global user.name "Michael Herrmann"

RUN apt-get install ruby ruby-dev build-essential -y && \
    gem install --no-ri --no-rdoc fpm

# Required for Python dependency pgi:
RUN apt-get install gobject-introspection libgtk-3-0 -y

# Add missing file libGL.so.1 for PyQt5.QtGui:
RUN apt-get install libgl1-mesa-glx -y

# Required for our use of reprepro:
RUN apt-get install reprepro expect -y

WORKDIR /root/dev/fman