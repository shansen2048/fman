from distutils.dir_util import copy_tree
from distutils.file_util import copy_file
from os.path import basename, normpath, join, exists, isfile, isdir
from PyQt5.QtWidgets import QMessageBox

class FileOperation:
	def __call__(self):
		raise NotImplementedError()

class CopyFiles(FileOperation):
	def __init__(self, files, dest_dir):
		self.files = files
		self.dest_dir = dest_dir
	def __call__(self):
		cannot_copy_to_self_shown = False
		override_all = None
		for src in self.files:
			name = basename(normpath(src))
			dest = join(self.dest_dir, name)
			if normpath(src) == normpath(dest):
				if not cannot_copy_to_self_shown:
					msgbox = QMessageBox()
					msgbox.setText("You cannot copy a file to itself.")
					msgbox.setStandardButtons(QMessageBox.Ok)
					msgbox.setDefaultButton(QMessageBox.Ok)
					msgbox.exec()
					cannot_copy_to_self_shown = True
				continue
			if exists(dest):
				if override_all is None:
					msgbox = QMessageBox()
					msgbox.setText(
						"%s exists. Do you want to override it?" % name
					)
					msgbox.setStandardButtons(
						QMessageBox.Yes | QMessageBox.No |
						QMessageBox.YesToAll | QMessageBox.NoToAll |
						QMessageBox.Abort
					)
					msgbox.setDefaultButton(QMessageBox.Yes)
					choice = msgbox.exec()
					if choice & QMessageBox.No:
						continue
					elif choice & QMessageBox.NoToAll:
						override_all = False
					elif choice & QMessageBox.YesToAll:
						override_all = True
					elif choice & QMessageBox.Abort:
						break
				if override_all is False:
					continue
			if isdir(src):
				copy_tree(src, dest)
			elif isfile(src):
				copy_file(src, dest)