FROM fedora:25

# Absolute minimum requirements for building a PyQt5 app with PyInstaller:
RUN dnf install -y libstdc++ freetype binutils

# Install fpm:
RUN dnf install -y ruby-devel gcc make rpm-build libffi-devel && \
    gem install --no-ri --no-rdoc fpm

# Required for Python dependency pgi:
RUN dnf install -y gobject-introspection

ADD gpg-agent.conf /root/.gnupg/gpg-agent.conf

RUN chmod -R 600 /root/.gnupg

ADD private.gpg-key public.gpg-key /tmp/

WORKDIR /tmp

RUN dnf install -y gpg rpm-sign && \
    gpg --batch --yes --passphrase ${gpg_pass} --import private.gpg-key public.gpg-key && \
    rpm --import public.gpg-key && \
    rm private.gpg-key public.gpg-key

ADD .rpmmacros /root

ADD .bashrc /root

WORKDIR /root/dev/fman