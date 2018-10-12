FROM fedora:25

# Absolute minimum requirements for building a PyQt5 app with PyInstaller:
RUN dnf install -y libstdc++ freetype binutils

# Install fpm:
RUN dnf install -y ruby-devel gcc make rpm-build libffi-devel && \
    gem install --no-ri --no-rdoc fpm

# Required for Python dependency pgi:
RUN dnf install -y gobject-introspection

ADD .bashrc /root/.bashrc

WORKDIR /root/dev/fman