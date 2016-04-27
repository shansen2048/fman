import sys

def is_windows():
	return sys.platform in ('win32', 'cygwin')

def is_osx():
	return sys.platform == 'darwin'

def is_linux():
	return sys.platform.startswith('linux')