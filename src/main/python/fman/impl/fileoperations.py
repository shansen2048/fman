from os import makedirs
from os.path import basename, join, exists, isdir, samefile, relpath, pardir, \
	dirname
from PyQt5.QtWidgets import QMessageBox
from shutil import copy2

import os

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
	def prompt_user(self, text, standard_buttons, default_button):
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
	def __init__(self, gui_thread, files, dest_dir, src_dir=None):
		super().__init__(gui_thread)
		self.files = files
		self.dest_dir = dest_dir
		self.src_dir = src_dir
		self.cannot_copy_to_self_shown = False
		self.override_all = None
	def __call__(self):
		for src in self.files:
			dest = self._get_dest_path(src)
			if isdir(src):
				makedirs(dest, exist_ok=True)
				for (dir_, _, file_names) in os.walk(src):
					for file_name in file_names:
						file_path = join(dir_, file_name)
						dest_ = self._get_dest_path(file_path)
						if not self.copy_file(file_path, dest_):
							break
			else:
				if not self.copy_file(src, dest):
					break
	def copy_file(self, src, dest):
		if exists(dest):
			if samefile(src, dest):
				if not self.cannot_copy_to_self_shown:
					self.prompt_user(
						"You cannot copy a file to itself.", Ok, Ok
					)
					self.cannot_copy_to_self_shown = True
				return True
			if self.override_all is None:
				choice = self.prompt_user(
					"%s exists. Do you want to override it?" % basename(src),
					Yes | No | YesToAll | NoToAll | Abort, Yes
				)
				if choice & No:
					return True
				elif choice & NoToAll:
					self.override_all = False
				elif choice & YesToAll:
					self.override_all = True
				elif choice & Abort:
					return False
			if self.override_all is False:
				return True
		makedirs(dirname(dest), exist_ok=True)
		copy2(src, dest)
		return True
	def _get_dest_path(self, src_file):
		if self.src_dir:
			rel_path = relpath(src_file, self.src_dir)
			is_in_src_dir = not rel_path.startswith(pardir)
			if is_in_src_dir:
				return join(self.dest_dir, rel_path)
		return join(self.dest_dir, basename(src_file))