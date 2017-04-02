import os
import sys

def is_windows():
	return sys.platform in ('win32', 'cygwin')

def is_mac():
	return sys.platform == 'darwin'

def is_linux():
	return sys.platform.startswith('linux')

def is_gnome_based():
	curr_desktop = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
	return curr_desktop in ('unity', 'gnome', 'x-cinnamon')