# Build on an old Arch version on purpose, to maximize compatibility:
FROM fmanbuildsystem/archlinux:2018.04.01

ARG requirements

# Use the files from arch-repo/ as our package repository. We previously simply
# used an online repository. But some of its files disappeared.
ADD arch-repo /tmp/arch-repo
RUN cd /tmp/arch-repo && repo-add repo.db.tar.gz *.pkg.tar.xz
RUN sed -i 's/^\[core\]$/#[core]/g' /etc/pacman.conf && \
    sed -i 's/^\[extra\]$/#[core]/g' /etc/pacman.conf && \
    sed -i 's/^\[community\]$/#[core]/g' /etc/pacman.conf && \
    sed -i 's|^Include = /etc/pacman.d/mirrorlist$|#Include = /etc/pacman.d/mirrorlist|g' /etc/pacman.conf && \
    sed -i 's/^SigLevel \+=.*/SigLevel = Never/g' /etc/pacman.conf && \
    echo -e '[repo]\nServer = file:///tmp/arch-repo' >> /etc/pacman.conf && \
    pacman -Sy

# Python 3.6:
RUN pacman -S --noconfirm python

# fpm:
RUN pacman -S --noconfirm ruby ruby-rdoc && \
    export PATH=$PATH:$(ruby -e "puts Gem.user_dir")/bin && \
    gem update && \
    gem install --no-ri --no-rdoc fpm

WORKDIR /root/${app_name}

# Set up virtual environment:
ADD *.txt /tmp/requirements/
RUN python -m venv venv && \
    venv/bin/python -m pip install -r "/tmp/requirements/${requirements}"
RUN rm -rf /tmp/requirements/

ADD .bashrc /root/.bashrc

# Import GPG key for code signing the installer:
ADD private-key.gpg public-key.gpg /tmp/
RUN gpg -q --batch --yes --passphrase ${gpg_pass} --import /tmp/private-key.gpg /tmp/public-key.gpg && \
    rm /tmp/private-key.gpg /tmp/public-key.gpg

ADD gpg-agent.conf /root/.gnupg/gpg-agent.conf
RUN gpgconf --kill gpg-agent

RUN pacman -S --noconfirm p7zip

RUN pacman -S --noconfirm git && \
    git config --global user.email "michael@herrmann.io" && \
    git config --global user.name "Michael Herrmann"

ADD id_rsa /root/.ssh/id_rsa
RUN chmod 600 /root/.ssh/id_rsa
ADD id_rsa.pub /root/.ssh/id_rsa.pub
RUN pacman -S --noconfirm openssh && \
    ssh-keyscan -H github.com >> ~/.ssh/known_hosts && \
    ssh-keyscan -H fman.io >> ~/.ssh/known_hosts && \
    chmod 600 ~/.ssh/known_hosts

RUN pacman -S --noconfirm rsync

# Support locale en_US.UTF-8. This is then activated in .bashrc.
RUN sed -i 's/#en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/g' /etc/locale.gen && \
    locale-gen