from os.path import splitdrive, exists
from PyQt5.QtWidgets import QFileDialog
from subprocess import Popen

import sys

class OS:
	def move_to_trash(self, *files):
		raise NotImplementedError()
	def prompt_user_to_pick_application(self, qt_parent, message):
		raise NotImplementedError()
	def open(self, file_, with_app=None):
		raise NotImplementedError()
	def open_terminal_in_directory(self, dir_):
		raise NotImplementedError()

class OSX(OS):
	def move_to_trash(self, *files):
		from osxtrash import move_to_trash
		return move_to_trash(*files)
	def prompt_user_to_pick_application(self, qt_parent, message):
		# Note: This import takes 200ms. Don't do it at the top of a file!
		from Cocoa import NSOpenPanel, NSURL, NSOKButton
		panel = NSOpenPanel.openPanel()
		panel.setDirectoryURL_(NSURL.fileURLWithPath_('/Applications'))
		panel.setCanChooseDirectories_(False)
		panel.setAllowedFileTypes_(['app'])
		panel.setMessage_(message)
		result = panel.runModal()
		if result == NSOKButton:
			return panel.filename()
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
	def prompt_user_to_pick_application(self, qt_parent, message):
		root_dir = r'c:\Program Files'
		if not exists(root_dir):
			root_dir = splitdrive(sys.executable)[0] + '\\'
		result = QFileDialog.getOpenFileName(
			qt_parent, message, root_dir, "Applications (*.exe)"
		)
		if result:
			return result[0]
	def open(self, file_, with_app=None):
		if with_app is None:
			from os import startfile
			startfile(file_)
		else:
			Popen([with_app, file_])
	def open_terminal_in_directory(self, dir_):
		Popen('start cmd', shell=True, cwd=dir_)