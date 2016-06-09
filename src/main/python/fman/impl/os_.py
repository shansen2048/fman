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
	def open(self, file_, with_app=None):
		raise NotImplementedError()
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
	def open(self, file_, with_app=None):
		args = ['/usr/bin/open']
		if with_app:
			args += ['-a', with_app]
		args.append(file_)
		Popen(args)
	def open_terminal_in_directory(self, dir_):
		self.open(dir_, with_app='Terminal')

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
	def open(self, file_, with_app=None):
		if with_app is None:
			from os import startfile
			startfile(file_)
		else:
			Popen([with_app, file_])
	def open_terminal_in_directory(self, dir_):
		Popen('start cmd', shell=True, cwd=dir_)