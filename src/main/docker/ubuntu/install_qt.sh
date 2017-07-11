#!/bin/sh

set -e

if [ -z $1 ]; then
	echo "Please supply the install location"
	exit 1
fi

# Install Qt's dependencies:
sudo apt-get install \
    build-essential libxcb1 libxcb1-dev libx11-xcb1 \
    libx11-xcb-dev libxcb-keysyms1 libxcb-keysyms1-dev libxcb-image0 \
    libxcb-image0-dev libxcb-shm0 libxcb-shm0-dev libxcb-icccm4 \
    libxcb-icccm4-dev libxcb-sync1 libxcb-sync-dev libxcb-xfixes0-dev \
    libxrender-dev libxcb-shape0-dev libxcb-randr0-dev libxcb-render-util0 \
    libxcb-render-util0-dev libxcb-glx0-dev libxcb-xinerama0-dev \
    libxrender-dev libfontconfig1-dev -y

sudo apt-get install curl dtrx -y

curl -O -L https://download.qt.io/official_releases/qt/5.6/5.6.2/single/qt-everywhere-opensource-src-5.6.2.7z
dtrx -n qt-everywhere-opensource-src-5.6.2.7z
cd qt-everywhere-opensource-src-5.6.2
./configure -prefix "$1" -release -opensource -no-accessibility -nomake examples -nomake tests -fontconfig --confirm-license
make -j4 module-qtbase module-qtsvg
make module-qtbase-install_subtargets module-qtsvg-install_subtargets
cd ..
rm -rf qt-everywhere-opensource-src-5.6.2 qt-everywhere-opensource-src-5.6.2.7z