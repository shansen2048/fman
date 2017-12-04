#!/bin/sh

# Requirements:
#  * p7zip (install with brew)
#  * Xcode

set -e

if [ -z $1 ]; then
	echo "Please supply the install location. Eg. ~/dev/fman/cache/Qt-5.6.2"
	exit 1
fi

curl -O -L https://download.qt.io/official_releases/qt/5.6/5.6.2/single/qt-everywhere-opensource-src-5.6.2.7z
7za x qt-everywhere-opensource-src-5.6.2.7z
patch -p0 -i qt.patch
cd qt-everywhere-opensource-src-5.6.2
./configure -prefix "$1"-release -opensource -no-accessibility -nomake examples -nomake tests -fontconfig --confirm-license
make -j2 module-qtbase module-qtsvg
make module-qtbase-install_subtargets module-qtsvg-install_subtargets
cd ..
rm -rf qt-everywhere-opensource-src-5.6.2.7z qt-everywhere-opensource-src-5.6.2