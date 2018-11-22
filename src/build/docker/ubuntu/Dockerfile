FROM ubuntu:14.04

RUN apt-get update && \
    apt-get upgrade -y

# Required for our use of reprepro:
ADD gpg-agent.conf gpg.conf /root/.gnupg/
# Avoid GPG warning "unsafe permissions":
RUN chmod -R 600 /root/.gnupg/
RUN apt-get install reprepro gnupg-agent gnupg2 -y
ADD private-key.gpg public-key.gpg /tmp/
RUN gpg -q --batch --yes --passphrase ${gpg_pass} --import /tmp/private-key.gpg /tmp/public-key.gpg && \
    rm /tmp/private-key.gpg /tmp/public-key.gpg

# Python 3.6:
RUN DEBIAN_FRONTEND=noninteractive apt-get install software-properties-common -y && \
    add-apt-repository ppa:deadsnakes/ppa -y && \
    apt-get update && \
    apt-get install python3.6 python3.6-dev python3.6-venv -y

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

# fpm:
RUN apt-get install ruby ruby-dev build-essential -y && \
    gem install --no-ri --no-rdoc fpm

# Required for Python dependency pgi:
RUN apt-get install gobject-introspection libgtk-3-0 -y

# Add missing file libGL.so.1 for PyQt5.QtGui:
RUN apt-get install libgl1-mesa-glx -y

RUN locale-gen en_US.UTF-8
ADD .bashrc /root/.bashrc

WORKDIR /root/dev/fman

ADD base.txt linux.txt ubuntu.txt /tmp/requirements/

RUN python3.6 -m venv venv && \
    venv/bin/python -m pip install -r /tmp/requirements/ubuntu.txt && \
    rm -rf /tmp/requirements/