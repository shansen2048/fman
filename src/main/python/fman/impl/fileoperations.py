from os import makedirs
from os.path import basename, join, exists, isdir, samefile, relpath, pardir
from PyQt5.QtWidgets import QMessageBox
from shutil import copy2, move, rmtree

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

class FileTreeOperation(FileOperation):
	def __init__(
		self, gui_thread, files, dest_dir, descr_verb, src_dir=None
	):
		super().__init__(gui_thread)
		self.files = files
		self.dest_dir = dest_dir
		self.descr_verb = descr_verb
		self.src_dir = src_dir
		self.cannot_move_to_self_shown = False
		self.override_all = None
	def __call__(self):
		for src in self.files:
			dest = self._get_dest_path(src)
			if isdir(src):
				if exists(dest) and samefile(src, dest):
					continue
				for (dir_, _, file_names) in os.walk(src):
					dest_dir = self._get_dest_path(dir_)
					makedirs(dest_dir, exist_ok=True)
					for file_name in file_names:
						file_path = join(dir_, file_name)
						dest_ = self._get_dest_path(file_path)
						if not self.perform_on_file(file_path, dest_):
							return
				self.postprocess_directory(src)
			else:
				if not self.perform_on_file(src, dest):
					return
	def perform_on_file(self, src, dest):
		if exists(dest):
			if samefile(src, dest):
				if not self.cannot_move_to_self_shown:
					self.prompt_user(
						"You cannot %s a file to itself." % self.descr_verb,
						Ok, Ok
					)
					self.cannot_move_to_self_shown = True
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
		self._perform_on_file(src, dest)
		return True
	def _perform_on_file(self, src, dest):
		raise NotImplementedError()
	def postprocess_directory(self, src_dir_path):
		pass
	def _get_dest_path(self, src_file):
		if self.src_dir:
			rel_path = relpath(src_file, self.src_dir)
			is_in_src_dir = not rel_path.startswith(pardir)
			if is_in_src_dir:
				return join(self.dest_dir, rel_path)
		return join(self.dest_dir, basename(src_file))

class CopyFiles(FileTreeOperation):
	def __init__(self, gui_thread, files, dest_dir, src_dir=None):
		super().__init__(gui_thread, files, dest_dir, 'copy', src_dir)
	def _perform_on_file(self, src, dest):
		copy2(src, dest, follow_symlinks=False)

class MoveFiles(FileTreeOperation):
	def __init__(self, gui_thread, files, dest_dir, src_dir=None):
		super().__init__(gui_thread, files, dest_dir, 'move', src_dir)
	def postprocess_directory(self, src_dir_path):
		rmtree(src_dir_path, ignore_errors=True)
	def _perform_on_file(self, src, dest):
		move(src, dest)
