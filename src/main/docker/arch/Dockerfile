FROM base/devel

ADD gpg-agent.conf /root/.gnupg/gpg-agent.conf
ADD .bashrc /root/.bashrc

WORKDIR /root/dev/fman

RUN pacman -Syu --noconfirm && \
    pacman -S --noconfirm python-pyqt5 git && \
    pacman -S --noconfirm ruby && \
    source ~/.bashrc && \
    gem install --no-ri --no-rdoc fpm && \
    gpgconf --kill gpg-agent