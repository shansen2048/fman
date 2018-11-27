# Build on an old Fedora version on purpose, to maximize compatibility:
FROM fedora:25

# Python 3.6:
RUN dnf install -y python36

# Absolute minimum requirements for building a PyQt5 app with PyInstaller:
RUN dnf install -y libstdc++ freetype binutils

# fpm:
RUN dnf install -y ruby-devel gcc make rpm-build libffi-devel && \
    gem install --no-ri --no-rdoc fpm

ADD .bashrc /root

WORKDIR /root/fman

# Required for Python dependency pgi - needs to be installed before setting up
# the venv:
RUN dnf install -y gobject-introspection

# Set up virtual environment:
ADD *.txt /tmp/requirements/
RUN python3.6 -m venv venv && \
    venv/bin/python -m pip install -r /tmp/requirements/fedora.txt
RUN rm -rf /tmp/requirements/

# The `release` build command calls git to check for uncommitted changes. So we
# need git:
RUN dnf install -y git

ADD gpg-agent.conf /root/.gnupg/gpg-agent.conf

RUN chmod -R 600 /root/.gnupg

ADD private-key.gpg public-key.gpg /tmp/

RUN dnf install -y createrepo_c

RUN dnf install -y gpg rpm-sign && \
    gpg -q --batch --yes --passphrase ${gpg_pass} --import /tmp/private-key.gpg /tmp/public-key.gpg && \
    rpm --import /tmp/public-key.gpg && \
    rm /tmp/private-key.gpg /tmp/public-key.gpg

ADD .rpmmacros /root

ENTRYPOINT ["/bin/bash"]