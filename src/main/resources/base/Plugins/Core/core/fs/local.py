from core.trash import move_to_trash
from datetime import datetime
from errno import ENOENT
from fman import PLATFORM
from fman.fs import FileSystem
from fman.url import as_url, splitscheme
from io import UnsupportedOperation
from os import remove
from os.path import isdir, getsize, getmtime, samefile, splitdrive
from pathlib import Path
from PyQt5.QtCore import QFileSystemWatcher
from shutil import rmtree, copytree, move, copyfile, copystat

class LocalFileSystem(FileSystem):

	scheme = 'file://'

	def __init__(self):
		super().__init__()
		self._watcher = None
	def get_default_columns(self, path):
		return 'NameColumn', 'SizeColumn', 'LastModifiedColumn'
	def exists(self, path):
		return Path(path).exists()
	def iterdir(self, path):
		for entry in Path(path).iterdir():
			yield entry.name
	def is_dir(self, path):
		return isdir(path)
	def get_size_bytes(self, path):
		return getsize(path)
	def get_modified_datetime(self, path):
		return datetime.fromtimestamp(getmtime(path))
	def touch(self, path):
		Path(path).touch()
	def mkdir(self, path):
		try:
			Path(path).mkdir()
		except FileNotFoundError:
			raise
		except OSError as e:
			if e.errno == ENOENT:
				raise FileNotFoundError(path) from e
			else:
				raise
	def move(self, src_url, dst_url):
		src_path, dst_path = self._get_src_dst_path(src_url, dst_url)
		move(src_path, dst_path)
	def move_to_trash(self, file_path):
		move_to_trash(file_path)
	def delete(self, path):
		if self.is_dir(path):
			rmtree(path)
		else:
			remove(path)
	def resolve(self, path):
		# Unlike other functions, Path#resolve can't handle C: instead of C:\
		path = self._add_backslash_to_drive_if_missing(path)
		return as_url(Path(path).resolve())
	def _add_backslash_to_drive_if_missing(self, file_path):
		"""
		Normalize "C:" -> "C:\". Required for some path functions on Windows.
		"""
		if PLATFORM == 'Windows' and file_path:
			drive_or_unc, path = splitdrive(file_path)
			is_drive = drive_or_unc.endswith(':')
			if is_drive and file_path == drive_or_unc:
				return file_path + '\\'
		return file_path
	def samefile(self, path1, path2):
		return samefile(path1, path2)
	def copy(self, src_url, dst_url):
		src_path, dst_path = self._get_src_dst_path(src_url, dst_url)
		if self.is_dir(src_path):
			copytree(src_path, dst_path, symlinks=True)
		else:
			copyfile(src_path, dst_path, follow_symlinks=False)
			copystat(src_path, dst_path, follow_symlinks=False)
	def watch(self, path):
		self._get_watcher().addPath(path)
	def unwatch(self, path):
		self._get_watcher().removePath(path)
	def _get_watcher(self):
		# Instantiate QFileSystemWatcher as late as possible. It requires a
		# QApplication which isn't available in some tests.
		if self._watcher is None:
			self._watcher = QFileSystemWatcher()
			self._watcher.directoryChanged.connect(self.notify_file_changed)
			self._watcher.fileChanged.connect(self.notify_file_changed)
		return self._watcher
	def _get_src_dst_path(self, src_url, dst_url):
		src_scheme, src_path = splitscheme(src_url)
		dst_scheme, dst_path = splitscheme(dst_url)
		if src_scheme != self.scheme or dst_scheme != self.scheme:
			raise UnsupportedOperation()
		return src_path, dst_path

if PLATFORM == 'Windows':

	class DrivesFileSystem(FileSystem):

		scheme = 'drives://'

		def get_default_columns(self, path):
			return 'NameColumn',
		def resolve(self, path):
			if not path:
				# Showing the list of all drives:
				return self.scheme
			if path in self._get_drives():
				return as_url(path + '\\')
			raise FileNotFoundError(path)
		def iterdir(self, path):
			if path:
				raise FileNotFoundError(path)
			return self._get_drives()
		def is_dir(self, path):
			return self.exists(path)
		def exists(self, path):
			return not path or path in self._get_drives()
		def _get_drives(self):
			from ctypes import windll
			import string
			result = []
			bitmask = windll.kernel32.GetLogicalDrives()
			for letter in string.ascii_uppercase:
				if bitmask & 1:
					result.append(letter + ':')
				bitmask >>= 1
			return result