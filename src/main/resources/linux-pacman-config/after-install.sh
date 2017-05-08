#!/bin/sh

set -e

pacman-key --add /opt/fman/public.gpg-key
pacman-key --lsign-key ${gpg_key}

if ! grep -qx "\[fman\]" /etc/pacman.conf ; then
	echo -e '\n[fman]\nInclude = /etc/pacman.d/fman' >> /etc/pacman.conf
fi