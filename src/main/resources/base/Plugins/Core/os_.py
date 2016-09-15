from fman import platform
from subprocess import Popen

def open_file_with_app(file_, app):
	if platform() == 'osx':
		Popen(['/usr/bin/open', '-a', app, file_])
	else:
		Popen([app, file_])

def open_terminal_in_directory(dir_path):
	if platform() == 'osx':
		open_file_with_app(dir_path, 'Terminal')
	elif platform() == 'windows':
		Popen('start cmd', shell=True, cwd=dir_path)
	elif platform() == 'linux':
		Popen('gnome-terminal', shell=True, cwd=dir_path)
	else:
		raise NotImplementedError(platform())

def open_native_file_manager(dir_path):
	if platform() == 'osx':
		open_file_with_app(dir_path, 'Finder')
	elif platform() == 'windows':
		Popen(['start', 'explorer', dir_path], shell=True)
	elif platform() == 'linux':
		Popen(['gnome-open', dir_path], shell=True)
	else:
		raise NotImplementedError(platform())