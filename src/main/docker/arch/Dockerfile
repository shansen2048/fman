FROM base/devel

RUN pacman -Syu --noconfirm

ADD gpg-agent.conf /root/.gnupg/gpg-agent.conf
RUN gpgconf --kill gpg-agent

ADD .bashrc /root/.bashrc

RUN pacman -S --noconfirm python-pyqt5

RUN pacman -S --noconfirm ruby && \
    source ~/.bashrc && \
    gem install --no-ri --no-rdoc fpm

RUN pacman -S --noconfirm git && \
    git config --global user.email "michael@herrmann.io" && \
    git config --global user.name "Michael Herrmann"

ADD id_rsa /root/.ssh/id_rsa
ADD id_rsa.pub /root/.ssh/id_rsa.pub
RUN pacman -S --noconfirm openssh && \
    ssh-keyscan -H dev.herrmann.io >> ~/.ssh/known_hosts && \
    ssh-keyscan -H fman.io >> ~/.ssh/known_hosts && \
    chmod 600 ~/.ssh/known_hosts

RUN pacman -S --noconfirm rsync

WORKDIR /root/dev/fman