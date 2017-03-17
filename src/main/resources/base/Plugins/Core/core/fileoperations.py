from fman import YES, NO, YES_TO_ALL, NO_TO_ALL, ABORT
from os import makedirs, listdir
from os.path import basename, join, exists, isdir, samefile, relpath, pardir, \
	dirname, isabs

# Work around http://bugs.python.org/issue21775.
# It affects both shutil.copytree(...) and shutil.move(...).
# TODO: Remove workaround once we are using a Python version > 3.4
import shutil
_copytree_original = shutil.copytree
def _copytree_patched(*args, **kwargs):
	try:
		return _copytree_original(*args, **kwargs)
	except AttributeError as e:
		raise OSError() from e
shutil.copytree = _copytree_patched

from shutil import copy2, move, rmtree, copytree

import os

class FileTreeOperation:
	def __init__(
		self, ui, files, dest_dir, descr_verb, src_dir=None, dest_name=None
	):
		if dest_name and len(files) > 1:
			raise ValueError(
				'Destination name can only be given when there is one file.'
			)
		self.ui = ui
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
			if not self._call_on_file(src):
				break
		self.ui.clear_status_message()
	def _call_on_file(self, src):
		if src.endswith('/'):
			# File paths ending in '/' screw up os.path.basename(...):
			raise ValueError(
				"Please ensure file paths don't end in '/', eg. by calling "
				"normpath(...)."
			)
		self._report_processing_of_file(src)
		dest = self._get_dest_path(src)
		try:
			if isdir(src):
				if exists(dest):
					if samefile(src, dest):
						return True
					else:
						for (dir_, _, file_names) in os.walk(src):
							for file_name in file_names:
								file_path = join(dir_, file_name)
								dst = self._get_dest_path(file_path)
								try:
									if not self.perform_on_file(file_path, dst):
										return False
								except (OSError, IOError):
									return self._handle_exception(file_path)
						self.postprocess_directory(src)
				else:
					self._perform_on_dir_dest_doesnt_exist(src, dest)
			else:
				if not self.perform_on_file(src, dest):
					return False
		except (OSError, IOError):
			return self._handle_exception(src)
		return True
	def _handle_exception(self, file_path):
		choice = self.ui.show_alert(
			'Could not %s %s. Do you want to continue?'
			% (self.descr_verb, file_path), YES | YES_TO_ALL | ABORT, YES
		)
		return choice & YES or choice & YES_TO_ALL
	def _report_processing_of_file(self, file_):
		verb = self.descr_verb.capitalize()
		if verb.endswith('e'):
			verb = verb[:-1]
		verbing = verb + 'ing'
		self.ui.show_status_message('%s %s...' % (verbing, basename(file_)))
	def perform_on_file(self, src, dest):
		self._report_processing_of_file(src)
		if exists(dest):
			if samefile(src, dest):
				if not self.cannot_move_to_self_shown:
					self.ui.show_alert(
						"You cannot %s a file to itself." % self.descr_verb
					)
					self.cannot_move_to_self_shown = True
				return True
			if self.override_all is None:
				choice = self.ui.show_alert(
					"%s exists. Do you want to overwrite it?" % basename(src),
					YES | NO | YES_TO_ALL | NO_TO_ALL | ABORT, YES
				)
				if choice & NO:
					return True
				elif choice & NO_TO_ALL:
					self.override_all = False
				elif choice & YES_TO_ALL:
					self.override_all = True
				elif choice & ABORT:
					return False
			if self.override_all is False:
				return True
		makedirs(dirname(dest), exist_ok=True)
		self._perform_on_file(src, dest)
		return True
	def postprocess_directory(self, src_dir_path):
		pass
	def _get_dest_path(self, src_file):
		dest_name = self.dest_name or basename(src_file)
		if self.src_dir:
			try:
				rel_path = \
					relpath(join(dirname(src_file), dest_name), self.src_dir)
			except ValueError as e:
				raise ValueError(
					'Could not construct path. '
					'src_file: %r, dest_name: %r, src_dir: %r' %
					(src_file, dest_name, self.src_dir)
				) from e
			is_in_src_dir = not rel_path.startswith(pardir)
			if is_in_src_dir:
				if isabs(self.dest_dir):
					return join(self.dest_dir, rel_path)
				else:
					return join(self.src_dir, self.dest_dir, rel_path)
		return join(self.dest_dir, dest_name)

class CopyFiles(FileTreeOperation):
	def __init__(
		self, ui, files, dest_dir, src_dir=None, dest_name=None
	):
		super().__init__(ui, files, dest_dir, 'copy', src_dir, dest_name)
	def _perform_on_dir_dest_doesnt_exist(self, src, dest):
		copytree(src, dest, symlinks=True)
	def _perform_on_file(self, src, dest):
		copy2(src, dest, follow_symlinks=False)

class MoveFiles(FileTreeOperation):
	def __init__(
		self, ui, files, dest_dir, src_dir=None, dest_name=None
	):
		super().__init__(ui, files, dest_dir, 'move', src_dir, dest_name)
	def postprocess_directory(self, src_dir_path):
		if not listdir(src_dir_path):
			rmtree(src_dir_path, ignore_errors=True)
	def _perform_on_dir_dest_doesnt_exist(self, src, dest):
		move(src, dest)
	def _perform_on_file(self, src, dest):
		move(src, dest)