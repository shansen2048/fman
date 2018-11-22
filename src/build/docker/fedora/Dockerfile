FROM fedora:25

# The `release` build command calls git to check for uncommitted changes. So we
# need git:
RUN dnf install -y git

# Absolute minimum requirements for building a PyQt5 app with PyInstaller:
RUN dnf install -y libstdc++ freetype binutils

# Install fpm:
RUN dnf install -y ruby-devel gcc make rpm-build libffi-devel && \
    gem install --no-ri --no-rdoc fpm

# Python 3.6:
RUN dnf install -y python36

# Required for Python dependency pgi:
RUN dnf install -y gobject-introspection

ADD gpg-agent.conf /root/.gnupg/gpg-agent.conf

RUN chmod -R 600 /root/.gnupg

ADD private.gpg-key public.gpg-key /tmp/

WORKDIR /tmp

RUN dnf install -y createrepo_c

RUN dnf install -y gpg rpm-sign && \
    gpg -q --batch --yes --passphrase ${gpg_pass} --import private.gpg-key public.gpg-key && \
    rpm --import public.gpg-key && \
    rm private.gpg-key public.gpg-key

ADD .rpmmacros /root

ADD .bashrc /root

WORKDIR /root/dev/fman

ADD base.txt linux.txt ubuntu.txt fedora.txt /tmp/requirements/

RUN python3.6 -m venv venv && \
    venv/bin/python -m pip install -r /tmp/requirements/fedora.txt && \
    rm -rf /tmp/requirements/

ENTRYPOINT ["/bin/bash"]