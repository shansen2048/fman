from os.path import splitdrive, exists
from subprocess import Popen

import sys

class OS:
	def move_to_trash(self, *files):
		raise NotImplementedError()
	def get_applications_directory(self):
		raise NotImplementedError()
	def get_applications_filter(self):
		raise NotImplementedError()
	def open_file_with_app(self, file_, app):
		Popen([app, file_])
	def open_terminal_in_directory(self, dir_):
		raise NotImplementedError()

class OSX(OS):
	def move_to_trash(self, *files):
		from osxtrash import move_to_trash
		return move_to_trash(*files)
	def get_applications_directory(self):
		return '/Applications'
	def get_applications_filter(self):
		return "Applications (*.app)"
	def open_file_with_app(self, file_, app):
		Popen(['/usr/bin/open', '-a', app, file_])
	def open_terminal_in_directory(self, dir_):
		self.open_file_with_app(dir_, 'Terminal')

class Windows(OS):
	def move_to_trash(self, *files):
		from send2trash import send2trash
		for file in files:
			send2trash(file)
	def get_applications_directory(self):
		result = r'c:\Program Files'
		if not exists(result):
			result = splitdrive(sys.executable)[0] + '\\'
		return result
	def get_applications_filter(self):
		return "Applications (*.exe)"
	def open_terminal_in_directory(self, dir_):
		Popen('start cmd', shell=True, cwd=dir_)

class Linux(OS):
	def move_to_trash(self, *files):
		from send2trash import send2trash
		for file in files:
			send2trash(file)
	def get_applications_directory(self):
		return r'/usr/bin'
	def get_applications_filter(self):
		return "Applications (*)"
	def open_terminal_in_directory(self, dir_):
		Popen('gnome-terminal', shell=True, cwd=dir_)