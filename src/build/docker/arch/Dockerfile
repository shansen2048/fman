FROM base/devel

# The mirrorlist from the default Docker image only lists a single mirror.
# If that mirror has problems, this image cannot be built. Avoid this by using
# the full list of mirrors:
RUN curl -o /etc/pacman.d/mirrorlist "https://www.archlinux.org/mirrorlist/?protocol=http&protocol=https&ip_version=4&use_mirror_status=on" && \
    sed -i 's/^#Server/Server/' /etc/pacman.d/mirrorlist && \
    pacman -Syyu --noconfirm

# Choose the best mirror:
RUN pacman -S --noconfirm reflector && \
    reflector --latest 10 --protocol http --protocol https --sort rate --save /etc/pacman.d/mirrorlist && \
    pacman -Syyu --noconfirm

ADD gpg-agent.conf /root/.gnupg/gpg-agent.conf
RUN gpgconf --kill gpg-agent

# Support locale en_US.UTF-8. This is then activated in .bashrc.
RUN sed -i 's/#en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/g' /etc/locale.gen && \
    locale-gen

ADD .bashrc /root/.bashrc

# Install Python 3.5. We need a separate user ("build-python35") for this
# because `makepkg` cannot be run as root.
RUN useradd -m --shell /bin/bash build-python35 && \
    echo 'build-python35 ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers
USER build-python35
WORKDIR /home/build-python35
ADD python35 /home/build-python35
RUN makepkg -si --noconfirm
USER root
WORKDIR /root
RUN userdel -r build-python35 && \
    sed -i '/build-python35 ALL=(ALL) NOPASSWD: ALL/d' /etc/sudoers

RUN pacman -S --noconfirm p7zip

RUN pacman -S --noconfirm ruby ruby-rdoc && \
    # Avoid error "cannot load such file -- ubygems":
    sed -i.bak "s/ -rubygems//g" ~/.bashrc && \
    source ~/.bashrc && \
    gem update && \
    gem install --no-ri --no-rdoc fpm

RUN pacman -S --noconfirm git && \
    git config --global user.email "michael@herrmann.io" && \
    git config --global user.name "Michael Herrmann"

ADD id_rsa /root/.ssh/id_rsa
RUN chmod 600 /root/.ssh/id_rsa
ADD id_rsa.pub /root/.ssh/id_rsa.pub
RUN pacman -S --noconfirm openssh && \
    ssh-keyscan -H dev.herrmann.io >> ~/.ssh/known_hosts && \
    ssh-keyscan -H fman.io >> ~/.ssh/known_hosts && \
    chmod 600 ~/.ssh/known_hosts

RUN pacman -S --noconfirm rsync

WORKDIR /root/dev/fman