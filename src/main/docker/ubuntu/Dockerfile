FROM ubuntu:14.04

RUN apt-get update && \
    apt-get upgrade -y

ADD install_qt.sh /tmp
ADD install_python35.sh /tmp

WORKDIR /tmp

RUN ./install_qt.sh ~/dev/fman/cache/Qt-5.6.2

RUN ./install_python35.sh
ENV LD_LIBRARY_PATH /usr/local/lib

ADD id_rsa /root/.ssh/id_rsa
ADD id_rsa.pub /root/.ssh/id_rsa.pub
RUN apt-get install openssh-client -y && \
    ssh-keyscan -H dev.herrmann.io >> ~/.ssh/known_hosts && \
    ssh-keyscan -H fman.io >> ~/.ssh/known_hosts && \
    chmod 600 ~/.ssh/known_hosts

RUN apt-get install git -y

RUN apt-get install ruby ruby-dev build-essential -y && \
    gem install --no-ri --no-rdoc fpm

# Required for Python dependency pgi:
RUN apt-get install gobject-introspection libgtk-3-0 -y

WORKDIR /root/dev/fman