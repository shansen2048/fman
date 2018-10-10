FROM fedora:25

# Absolute minimum requirements for building a PyQt5 app with PyInstaller:
RUN dnf install -y libstdc++ freetype binutils

# Required for Python dependency pgi:
RUN dnf install -y gobject-introspection

ADD .bashrc /root/.bashrc

WORKDIR /root/dev/fman