from fman import PLATFORM
from subprocess import Popen

def open_file_with_app(file_, app):
	if PLATFORM == 'Mac':
		Popen(['/usr/bin/open', '-a', app, file_])
	else:
		Popen([app, file_])

def open_terminal_in_directory(dir_path):
	if PLATFORM == 'Mac':
		open_file_with_app(dir_path, 'Terminal')
	elif PLATFORM == 'Windows':
		Popen('start cmd', shell=True, cwd=dir_path)
	elif PLATFORM == 'Linux':
		Popen('gnome-terminal', shell=True, cwd=dir_path)
	else:
		raise NotImplementedError(PLATFORM)

def open_native_file_manager(dir_path):
	if PLATFORM == 'Mac':
		open_file_with_app(dir_path, 'Finder')
	elif PLATFORM == 'Windows':
		Popen(['start', 'explorer', dir_path], shell=True)
	elif PLATFORM == 'Linux':
		Popen(['gnome-open', dir_path], shell=True)
	else:
		raise NotImplementedError(PLATFORM)