#!/bin/sh

set -e

# Would like Python 3.5 here but build-dep for it
# is not available on Ubuntu 14.04.
sudo apt-get build-dep python3.4 -y

sudo apt-get install curl dtrx -y

curl -O -L https://www.python.org/ftp/python/3.5.3/Python-3.5.3.tar.xz
dtrx -n Python-3.5.3.tar.xz
cd Python-3.5.3
./configure --enable-shared --enable-optimizations
make
sudo make install
cd ..
rm -rf Python-3.5.3 Python-3.5.3.tar.xz