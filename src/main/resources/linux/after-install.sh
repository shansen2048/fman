#!/bin/sh
set -e
apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv ${gpg_key}
(crontab -l ; echo "`date +'%M %H'` * * * update-fman") | crontab -