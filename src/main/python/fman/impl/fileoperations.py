from distutils.dir_util import copy_tree
from distutils.file_util import copy_file
from os.path import basename, normpath, join, exists, isfile, isdir
from PyQt5.QtWidgets import QMessageBox

Yes = QMessageBox.Yes
No = QMessageBox.No
YesToAll = QMessageBox.YesToAll
NoToAll = QMessageBox.NoToAll
Abort = QMessageBox.Abort
Ok = QMessageBox.Ok

class FileOperation:
	def __init__(self, gui_thread):
		self.gui_thread = gui_thread
	def __call__(self):
		raise NotImplementedError()
	def show_message_box(self, text, standard_buttons, default_button):
		return self.gui_thread.execute(
			self._show_message_box, text, standard_buttons, default_button
		)
	def _show_message_box(self, text, standard_buttons, default_button):
		msgbox = QMessageBox()
		msgbox.setText(text)
		msgbox.setStandardButtons(standard_buttons)
		msgbox.setDefaultButton(default_button)
		return msgbox.exec()

class CopyFiles(FileOperation):
	def __init__(self, gui_thread, files, dest_dir):
		super().__init__(gui_thread)
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
					self.show_message_box(
						"You cannot copy a file to itself.", Ok, Ok
					)
					cannot_copy_to_self_shown = True
				continue
			if exists(dest):
				if override_all is None:
					choice = self.show_message_box(
						"%s exists. Do you want to override it?" % name,
						Yes | No | YesToAll | NoToAll | Abort, Yes
					)
					if choice & No:
						continue
					elif choice & NoToAll:
						override_all = False
					elif choice & YesToAll:
						override_all = True
					elif choice & Abort:
						break
				if override_all is False:
					continue
			if isdir(src):
				copy_tree(src, dest)
			elif isfile(src):
				copy_file(src, dest)