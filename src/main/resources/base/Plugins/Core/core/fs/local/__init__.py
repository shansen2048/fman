from core.trash import move_to_trash
from core.util import filenotfounderror
from datetime import datetime
from errno import ENOENT
from fman import PLATFORM, Task
from fman.fs import FileSystem, cached
from fman.impl.util.qt.thread import run_in_main_thread
from fman.url import as_url, splitscheme, as_human_readable, join, basename, \
	dirname
from io import UnsupportedOperation
from os import remove
from os.path import islink, samestat
from pathlib import Path
from PyQt5.QtCore import QFileSystemWatcher
from shutil import copystat
from stat import S_ISDIR

import os

if PLATFORM == 'Windows':
	from core.fs.local.windows.rmtree import rmtree
	from core.fs.local.windows.drives import DrivesFileSystem, DriveName
	from core.fs.local.windows.network import NetworkFileSystem
else:
	from shutil import rmtree

class LocalFileSystem(FileSystem):

	scheme = 'file://'

	def __init__(self):
		super().__init__()
		self._watcher = None
	def get_default_columns(self, path):
		return 'core.Name', 'core.Size', 'core.Modified'
	def exists(self, path):
		return Path(self._url_to_os_path(path)).exists()
	def iterdir(self, path):
		for entry in Path(self._url_to_os_path(path)).iterdir():
			yield entry.name
	def is_dir(self, existing_path):
		# Like Python's isdir(...) except raises FileNotFoundError if the file
		# does not exist and OSError if there is another error.
		return S_ISDIR(self.stat(existing_path).st_mode)
	@cached
	def stat(self, path):
		return os.stat(self._url_to_os_path(path))
	def size_bytes(self, path):
		return self.stat(path).st_size
	def modified_datetime(self, path):
		return datetime.fromtimestamp(self.stat(path).st_mtime)
	def touch(self, path):
		os_path = Path(self._url_to_os_path(path))
		try:
			os_path.touch(exist_ok=False)
		except FileExistsError:
			os_path.touch(exist_ok=True)
		else:
			self.notify_file_added(path)
	def mkdir(self, path):
		os_path = Path(self._url_to_os_path(path))
		try:
			os_path.mkdir()
		except FileNotFoundError:
			raise
		except IsADirectoryError: # macOS
			raise FileExistsError(path)
		except OSError as e:
			if e.errno == ENOENT:
				raise filenotfounderror(path) from e
			elif os_path.exists():
				# On at least Windows, Path('Z:\\').mkdir() raises
				# PermissionError instead of FileExistsError. We want the latter
				# however because #makedirs(...) relies on it. So handle this
				# case generally here:
				raise FileExistsError(path) from e
			else:
				raise
		self.notify_file_added(path)
	def move(self, src_url, dst_url):
		self._check_scheme(src_url, dst_url)
		for task in self._prepare_move(src_url, dst_url):
			task()
	def prepare_move(self, src_url, dst_url):
		self._check_scheme(src_url, dst_url)
		return self._prepare_move(src_url, dst_url, measure_size=True)
	def _prepare_move(self, src_url, dst_url, measure_size=False):
		src_path, dst_path = self._check_scheme(src_url, dst_url)
		src_stat = self.stat(src_path)
		dst_dir_dev = self.stat(splitscheme(dirname(dst_url))[1]).st_dev
		os_src_path = self._url_to_os_path(src_path)
		os_dst_path = self._url_to_os_path(dst_path)
		notify_file_moved = Task(
			'Postprocessing', target=self.notify_file_moved,
			args=(src_url, dst_url)
		)
		if src_stat.st_dev == dst_dir_dev:
			yield Task(
				'Moving ' + basename(src_url),
				target=Path(os_src_path).replace, args=(os_dst_path,), size=1
			)
			yield notify_file_moved
			return
		yield from self._prepare_copy(src_url, dst_url, measure_size)
		yield Task(
			'Postprocessing ' + basename(src_url),
			target=self.delete, args=(src_path,)
		)
		yield notify_file_moved
	def move_to_trash(self, path):
		move_to_trash(self._url_to_os_path(path))
		self.notify_file_removed(path)
	def delete(self, path):
		if self.is_dir(path):
			def handle_error(func, path, exc_info):
				if not isinstance(exc_info[1], FileNotFoundError):
					raise
			rmtree(self._url_to_os_path(path), onerror=handle_error)
		else:
			remove(self._url_to_os_path(path))
		self.notify_file_removed(path)
	def resolve(self, path):
		if not path:
			raise filenotfounderror(path)
		path = self._url_to_os_path(path)
		if PLATFORM == 'Windows':
			is_unc_server = path.startswith(r'\\') and not '\\' in path[2:]
			if is_unc_server:
				# Python can handle \\server\folder but not \\server. Defer to
				# the network:// file system.
				return 'network://' + path[2:]
		try:
			path = Path(path).resolve()
		except FileNotFoundError:
			# TODO: Remove this except block once we upgraded to Python >= 3.6.
			# In Python 3.5 on Windows, Path#resolve(...) raises
			# FileNotFoundError for virtual drives such as for instance X:
			# created by BoxCryptor.
			if not Path(path).exists():
				raise
		return as_url(path)
	def samefile(self, path1, path2):
		return samestat(self.stat(path1), self.stat(path2))
	def copy(self, src_url, dst_url):
		self._check_scheme(src_url, dst_url)
		for task in self._prepare_copy(src_url, dst_url):
			task()
	def prepare_copy(self, src_url, dst_url):
		self._check_scheme(src_url, dst_url)
		return self._prepare_copy(src_url, dst_url, measure_size=True)
	def _prepare_copy(self, src_url, dst_url, measure_size=False):
		src_path, dst_path = self._check_scheme(src_url, dst_url)
		src_is_dir = self.is_dir(src_path)
		if src_is_dir:
			yield Task(
				'Creating ' + basename(dst_url),
				target=self.mkdir, args=(dst_path,)
			)
			for name in self.iterdir(src_path):
				try:
					yield from self._prepare_copy(
						join(src_url, name), join(dst_url, name), measure_size
					)
				except FileNotFoundError:
					pass
		else:
			size = self.size_bytes(src_path) if measure_size else 0
			yield CopyFile(self, src_url, dst_url, size)
	@run_in_main_thread
	def watch(self, path):
		self._get_watcher().addPath(self._url_to_os_path(path))
	@run_in_main_thread
	def unwatch(self, path):
		self._get_watcher().removePath(self._url_to_os_path(path))
	def _get_watcher(self):
		# Instantiate QFileSystemWatcher as late as possible. It requires a
		# QApplication which isn't available in some tests.
		if self._watcher is None:
			self._watcher = QFileSystemWatcher()
			self._watcher.directoryChanged.connect(self._on_file_changed)
			self._watcher.fileChanged.connect(self._on_file_changed)
		return self._watcher
	def _on_file_changed(self, file_path):
		path_forward_slashes = splitscheme(as_url(file_path))[1]
		self.notify_file_changed(path_forward_slashes)
	def _check_scheme(self, src_url, dst_url):
		src_scheme, src_path = splitscheme(src_url)
		dst_scheme, dst_path = splitscheme(dst_url)
		if src_scheme != self.scheme or dst_scheme != self.scheme:
			raise UnsupportedOperation()
		return src_path, dst_path
	def _url_to_os_path(self, path):
		# Convert a "URL path" a/b to a path understood by the OS, eg. a\b on
		# Windows. An important effect of this function is that it turns
		# C: -> C:\. This is required for Python functions such as Path#resolve.
		return as_human_readable(self.scheme + path)

class CopyFile(Task):
	def __init__(self, fs, src_url, dst_url, size_bytes):
		super().__init__('Copying ' + basename(src_url), size=size_bytes)
		self._fs = fs
		self._src_url = src_url
		self._dst_url = dst_url
	def __call__(self):
		dst_urlpath = splitscheme(self._dst_url)[1]
		dst_existed = self._fs.exists(dst_urlpath)
		src = as_human_readable(self._src_url)
		dst = as_human_readable(self._dst_url)
		if islink(src):
			os.symlink(os.readlink(src), dst)
		else:
			with open(src, 'rb') as fsrc:
				with open(dst, 'wb') as fdst:
					num_written = 0
					while not self.was_canceled():
						buf = fsrc.read(16 * 1024)
						if not buf:
							break
						num_written += fdst.write(buf)
						self.set_progress(num_written)
		if not self.was_canceled():
			copystat(src, dst, follow_symlinks=False)
		if not dst_existed:
			self._fs.notify_file_added(dst_urlpath)