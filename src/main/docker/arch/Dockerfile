FROM base/devel

ADD gpg-agent.conf /root/.gnupg/gpg-agent.conf
ADD .bashrc /root/.bashrc

RUN pacman -Syu --noconfirm && \
    pacman -S --noconfirm python-pyqt5 git && \
    pacman -S --noconfirm ruby && \
    source ~/.bashrc && \
    gem install --no-ri --no-rdoc fpm && \
    gpgconf --kill gpg-agent

ADD id_rsa /root/.ssh/id_rsa
ADD id_rsa.pub /root/.ssh/id_rsa.pub

RUN pacman -S --noconfirm openssh && \
    ssh-keyscan -H dev.herrmann.io >> ~/.ssh/known_hosts ; chmod 600 ~/.ssh/known_hosts

WORKDIR /root/dev/fman