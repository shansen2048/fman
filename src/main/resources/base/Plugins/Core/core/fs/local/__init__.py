from core.trash import move_to_trash
from core.util import filenotfounderror
from datetime import datetime
from errno import ENOENT
from fman import PLATFORM
from fman.fs import FileSystem, Column
from fman.url import as_url, splitscheme
from io import UnsupportedOperation
from os import remove
from os.path import getsize, getmtime, samefile, splitdrive
from pathlib import Path
from PyQt5.QtCore import QFileSystemWatcher
from shutil import copytree, move, copyfile, copystat
from stat import S_ISDIR

import os

if PLATFORM == 'Windows':
	from core.fs.local.rmtree_windows import rmtree
else:
	from shutil import rmtree

class LocalFileSystem(FileSystem):

	scheme = 'file://'

	def __init__(self):
		super().__init__()
		self._watcher = None
	def get_default_columns(self, path):
		return 'Name', 'Size', 'Modified'
	def exists(self, path):
		return Path(path).exists()
	def iterdir(self, path):
		for entry in Path(path).iterdir():
			yield entry.name
	def is_dir(self, existing_path):
		# Like Python's isdir(...) except raises FileNotFoundError if the file
		# does not exist and OSError if there is another error.
		return S_ISDIR(os.stat(existing_path).st_mode)
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
				raise filenotfounderror(path) from e
			else:
				raise
	def move(self, src_url, dst_url):
		src_path, dst_path = self._get_src_dst_path(src_url, dst_url)
		move(src_path, dst_path)
	def move_to_trash(self, path):
		move_to_trash(path)
	def delete(self, path):
		if self.is_dir(path):
			self._delete_directory(path)
		else:
			remove(path)
	def _delete_directory(self, path):
		def handle_error(func, path, exc_info):
			if not isinstance(exc_info[1], FileNotFoundError):
				raise
		rmtree(path, onerror=handle_error)
	def resolve(self, path):
		if not path:
			raise filenotfounderror(path)
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
			return 'DriveName',
		def resolve(self, path):
			if not path:
				# Showing the list of all drives:
				return self.scheme
			if path in self._get_drives():
				return as_url(path + '\\')
			raise filenotfounderror(path)
		def iterdir(self, path):
			if path:
				raise filenotfounderror(path)
			return self._get_drives()
		def is_dir(self, existing_path):
			if not self.exists(existing_path):
				raise filenotfounderror(existing_path)
			return True
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

	class DriveName(Column):

		name = 'Name'

		def get_str(self, url):
			scheme, path = splitscheme(url)
			if scheme != 'drives://':
				raise ValueError('Unsupported URL: %r' % url)
			result = path
			try:
				vol_name = self._get_volume_name(path + '\\')
			except WindowsError:
				pass
			else:
				if vol_name:
					result += ' ' + vol_name
			return result
		def _get_volume_name(self, volume_path):
			import ctypes
			kernel32 = ctypes.windll.kernel32
			buffer = ctypes.create_unicode_buffer(1024)
			if not kernel32.GetVolumeInformationW(
				ctypes.c_wchar_p(volume_path), buffer, ctypes.sizeof(buffer),
				None, None, None, None, 0
			):
				raise ctypes.WinError()
			return buffer.value