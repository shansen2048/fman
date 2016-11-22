#!/bin/sh
# When we don't specify an --after-upgrade script for fpm, --after-install is
# called after upgrades as well (according to the fpm documentation, in order to
# preserve backwards compatibility). We therefore have this script here - even
# though it is currently empty - to ensure that our --after-install script
# is not called after mere upgrades as well.