#!/bin/sh
set -e
perl -i~ -0777 -pe 's:\n\[fman\]\nInclude = /etc/pacman.d/fman\n::g' /etc/pacman.conf