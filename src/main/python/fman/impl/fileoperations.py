from fman.impl.gui_operations import show_message_box
from fman.util.qt import Yes, No, YesToAll, NoToAll, Abort, Ok
from os import makedirs
from os.path import basename, join, exists, isdir, samefile, relpath, pardir, \
	dirname
from shutil import copy2, move, rmtree, copytree

import os

class FileTreeOperation:
	def __init__(
		self, gui_thread, status_bar, files, dest_dir, descr_verb, src_dir=None,
		dest_name=None
	):
		if dest_name and len(files) > 1:
			raise ValueError(
				'Destination name can only be given when there is one file.'
			)
		self.gui_thread = gui_thread
		self.status_bar = status_bar
		self.files = files
		self.dest_dir = dest_dir
		self.descr_verb = descr_verb
		self.src_dir = src_dir
		self.dest_name = dest_name
		self.cannot_move_to_self_shown = False
		self.override_all = None
	def _perform_on_dir_dest_doesnt_exist(self, src, dest):
		raise NotImplementedError()
	def _perform_on_file(self, src, dest):
		raise NotImplementedError()
	def __call__(self):
		for src in self.files:
			self._report_processing_of_file(src)
			dest = self._get_dest_path(src)
			if isdir(src):
				if exists(dest):
					if samefile(src, dest):
						continue
					else:
						for (dir_, _, file_names) in os.walk(src):
							dest_dir = self._get_dest_path(dir_)
							makedirs(dest_dir, exist_ok=True)
							for file_name in file_names:
								file_path = join(dir_, file_name)
								dst = self._get_dest_path(file_path)
								if not self.perform_on_file(file_path, dst):
									return
						self.postprocess_directory(src)
				else:
					self._perform_on_dir_dest_doesnt_exist(src, dest)
			else:
				if not self.perform_on_file(src, dest):
					return
		self._set_status('Ready.')
	def _report_processing_of_file(self, file_):
		verbing = self.descr_verb.capitalize() + 'ing'
		self._set_status('%s %s...' % (verbing, basename(file_)))
	def _set_status(self, status):
		self.gui_thread.execute(self.status_bar.showMessage, status)
	def perform_on_file(self, src, dest):
		self._report_processing_of_file(src)
		if exists(dest):
			if samefile(src, dest):
				if not self.cannot_move_to_self_shown:
					self._prompt_user(
						"You cannot %s a file to itself." % self.descr_verb,
						Ok, Ok
					)
					self.cannot_move_to_self_shown = True
				return True
			if self.override_all is None:
				choice = self._prompt_user(
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
		self._perform_on_file(src, dest)
		return True
	def _prompt_user(self, text, standard_buttons, default_button):
		return self.gui_thread.execute(
			show_message_box, text, standard_buttons, default_button
		)
	def postprocess_directory(self, src_dir_path):
		pass
	def _get_dest_path(self, src_file):
		dest_name = self.dest_name or basename(src_file)
		if self.src_dir:
			rel_path = relpath(join(dirname(src_file), dest_name), self.src_dir)
			is_in_src_dir = not rel_path.startswith(pardir)
			if is_in_src_dir:
				return join(self.dest_dir, rel_path)
		return join(self.dest_dir, dest_name)

class CopyFiles(FileTreeOperation):
	def __init__(
		self, gui_thread, status_bar, files, dest_dir, src_dir=None,
		dest_name=None
	):
		super().__init__(
			gui_thread, status_bar, files, dest_dir, 'copy', src_dir, dest_name
		)
	def _perform_on_dir_dest_doesnt_exist(self, src, dest):
		copytree(src, dest, symlinks=True)
	def _perform_on_file(self, src, dest):
		copy2(src, dest, follow_symlinks=False)

class MoveFiles(FileTreeOperation):
	def __init__(
		self, gui_thread, status_bar, files, dest_dir, src_dir=None,
		dest_name=None
	):
		super().__init__(
			gui_thread, status_bar, files, dest_dir, 'move', src_dir, dest_name
		)
	def postprocess_directory(self, src_dir_path):
		rmtree(src_dir_path, ignore_errors=True)
	def _perform_on_dir_dest_doesnt_exist(self, src, dest):
		move(src, dest)
	def _perform_on_file(self, src, dest):
		move(src, dest)
