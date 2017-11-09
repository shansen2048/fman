from fman import YES, NO, YES_TO_ALL, NO_TO_ALL, ABORT
from fman.url import basename, join, dirname, splitscheme, relpath
from os.path import pardir

import fman.fs

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
		self._report_processing_of_file(src)
		dest = self._get_dest_url(src)
		try:
			if fman.fs.is_dir(src):
				if fman.fs.exists(dest):
					if fman.fs.samefile(src, dest):
						return True
					else:
						for file_url in self._walk(src):
							dst = self._get_dest_url(file_url)
							try:
								if not self.perform_on_file(file_url, dst):
									return False
							except (OSError, IOError):
								return self._handle_exception(file_url)
						self.postprocess_directory(src)
				else:
					self._perform_on_dir_dest_doesnt_exist(src, dest)
			else:
				if not self.perform_on_file(src, dest):
					return False
		except (OSError, IOError):
			return self._handle_exception(src)
		return True
	def _walk(self, url):
		dirs = []
		nondirs = []
		for file_name in fman.fs.iterdir(url):
			file_url = join(url, file_name)
			try:
				is_dir = fman.fs.is_dir(file_url)
			except OSError:
				is_dir = False
			if is_dir:
				dirs.append(file_url)
			else:
				nondirs.append(file_url)
		yield from nondirs
		for dir_ in dirs:
			yield from self._walk(join(url, dir_))
	def _handle_exception(self, file_path):
		choice = self.ui.show_alert(
			'Could not %s %s. Do you want to continue?'
			% (self.descr_verb, file_path), YES | YES_TO_ALL | ABORT, YES
		)
		return choice & YES or choice & YES_TO_ALL
	def _report_processing_of_file(self, file_):
		verb = self.descr_verb.capitalize()
		verbing = (verb[:-1] if verb.endswith('e') else verb) + 'ing'
		self.ui.show_status_message('%s %s...' % (verbing, basename(file_)))
	def perform_on_file(self, src, dest):
		self._report_processing_of_file(src)
		if fman.fs.exists(dest):
			if fman.fs.samefile(src, dest):
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
		fman.fs.makedirs(dirname(dest), exist_ok=True)
		self._perform_on_file(src, dest)
		return True
	def postprocess_directory(self, src_dir_path):
		pass
	def _get_dest_url(self, src_file):
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
				try:
					splitscheme(self.dest_dir)
				except ValueError as no_scheme:
					return join(self.src_dir, self.dest_dir, rel_path)
				else:
					return join(self.dest_dir, rel_path)
		return join(self.dest_dir, dest_name)

class CopyFiles(FileTreeOperation):
	def __init__(self, ui, files, dest_dir, src_dir=None, dest_name=None):
		super().__init__(ui, files, dest_dir, 'copy', src_dir, dest_name)
	def _perform_on_dir_dest_doesnt_exist(self, src, dest):
		fman.fs.copy(src, dest)
	def _perform_on_file(self, src, dest):
		fman.fs.copy(src, dest)

class MoveFiles(FileTreeOperation):
	def __init__(self, ui, files, dest_dir, src_dir=None, dest_name=None):
		super().__init__(ui, files, dest_dir, 'move', src_dir, dest_name)
	def postprocess_directory(self, src_dir_path):
		if self._is_empty(src_dir_path):
			try:
				fman.fs.delete(src_dir_path)
			except OSError:
				pass
	def _is_empty(self, dir_url):
		try:
			next(iter(fman.fs.iterdir(dir_url)))
		except StopIteration:
			return True
		return False
	def _perform_on_dir_dest_doesnt_exist(self, src, dest):
		fman.fs.move(src, dest)
	def _perform_on_file(self, src, dest):
		fman.fs.move(src, dest)