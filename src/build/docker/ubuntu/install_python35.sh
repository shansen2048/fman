#!/bin/sh

set -e

sudo apt-get install curl dtrx -y

# Install the build dependencies for Python 3.5.3:
# Required for mk-build-deps:
sudo apt-get install devscripts equivs -y
mk-build-deps -i python3.5_3.5.3-1.dsc -r -t "apt-get -y"

curl -O -L https://www.python.org/ftp/python/3.5.3/Python-3.5.3.tar.xz
dtrx -n Python-3.5.3.tar.xz
cd Python-3.5.3
./configure --enable-shared --enable-optimizations
make
sudo make altinstall
cd ..
rm -rf Python-3.5.3 Python-3.5.3.tar.xz