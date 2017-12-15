import sys

def is_windows():
	return sys.platform in ('win32', 'cygwin')

def is_mac():
	return sys.platform == 'darwin'

def is_linux():
	return sys.platform.startswith('linux')

def is_ubuntu():
	with open('/etc/issue', 'r') as f:
		return f.read().startswith('Ubuntu ')

def is_arch_linux():
	with open('/etc/issue', 'r') as f:
		return f.read().startswith('Arch Linux ')