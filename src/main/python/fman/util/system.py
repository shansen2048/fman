import sys

def is_windows():
	return sys.platform in ('win32', 'cygwin')

def is_osx():
	return sys.platform == 'darwin'

def is_linux():
	return sys.platform.startswith('linux')

def get_canonical_os_name():
	if is_windows():
		return 'windows'
	if is_osx():
		return 'osx'
	if is_linux():
		return 'linux'
	raise ValueError('Unknown operating system.')