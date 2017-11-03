from datetime import datetime
from errno import ENOENT
from fman import PLATFORM
from fman.url import as_file_url
from fman.util.path import add_backslash_to_drive_if_missing, parent
from fman.impl.trash import move_to_trash
from math import log
from os import remove
from os.path import isdir, getsize, getmtime, basename, isfile, samefile
from pathlib import Path
from PyQt5.QtCore import QFileSystemWatcher
from shutil import rmtree, copytree, move, copyfile, copystat
from threading import Lock

import fman.fs
import re

class FileSystem:

	scheme = ''

	def __init__(self):
		self._file_changed_callbacks = {}
		self._file_changed_callbacks_lock = Lock()
	def parent(self, path):
		return parent(path)
	def watch(self, path):
		pass
	def unwatch(self, path):
		pass
	def notify_file_changed(self, path):
		for callback in self._file_changed_callbacks.get(path, []):
			callback(self.scheme + path)
	def samefile(self, f1, f2):
		return self.resolve(f1) == self.resolve(f2)
	def makedirs(self, path, exist_ok=True):
		# Copied / adapted from pathlib.Path#mkdir(...).
		try:
			self.mkdir(path)
		except FileExistsError:
			if not exist_ok or not self.isdir(path):
				raise
		except OSError as e:
			if e.errno != ENOENT:
				raise
			self.makedirs(self.parent(path))
			self.mkdir(path)
	def mkdir(self, path):
		"""
		Should raise FileExistsError if `path` already exists. If `path` is in
		a directory that does not yet exist, should raise an OSError with
		.errno = ENOENT. Typically this would be FileNotFoundError(ENOENT, ...).
		"""
		raise NotImplementedError()
	def getsize(self, path):
		return None
	def getmtime(self, path):
		return None
	def _add_file_changed_callback(self, path, callback):
		with self._file_changed_callbacks_lock:
			try:
				self._file_changed_callbacks[path].append(callback)
			except KeyError:
				self._file_changed_callbacks[path] = [callback]
				self.watch(path)
	def _remove_file_changed_callback(self, path, callback):
		with self._file_changed_callbacks_lock:
			path_callbacks = self._file_changed_callbacks[path]
			path_callbacks.remove(callback)
			if not path_callbacks:
				del self._file_changed_callbacks[path]
				self.unwatch(path)

class DefaultFileSystem(FileSystem):

	scheme = 'file://'

	def __init__(self):
		super().__init__()
		self._watcher = QFileSystemWatcher()
		self._watcher.directoryChanged.connect(self.notify_file_changed)
		self._watcher.fileChanged.connect(self.notify_file_changed)
	def exists(self, path):
		return Path(path).exists()
	def iterdir(self, path):
		for entry in Path(path).iterdir():
			yield entry.name
	# TODO: Rename to is_dir
	def isdir(self, path):
		return isdir(path)
	# TODO: Rename to is_file
	def isfile(self, path):
		return isfile(path)
	def getsize(self, path):
		return getsize(path)
	def getmtime(self, path):
		return getmtime(path)
	def touch(self, path):
		Path(path).touch()
	def mkdir(self, path):
		Path(path).mkdir()
	def move(self, old_path, new_path):
		move(old_path, new_path)
	def move_to_trash(self, file_path):
		move_to_trash(file_path)
	def delete(self, path):
		if self.isdir(path):
			rmtree(path)
		else:
			remove(path)
	def resolve(self, path):
		# Unlike other functions, Path#resolve can't handle C: instead of C:\
		path = add_backslash_to_drive_if_missing(path)
		return as_file_url(Path(path).resolve())
	def samefile(self, f1, f2):
		return samefile(f1, f2)
	def parent(self, path):
		# Unlike other functions, Path#parent can't handle C: instead of C:\
		path = add_backslash_to_drive_if_missing(path)
		return Path(path).parent.as_posix()
	def copy(self, src, dst):
		if self.isdir(src):
			copytree(src, dst, symlinks=True)
		else:
			copyfile(src, dst, follow_symlinks=False)
			copystat(src, dst, follow_symlinks=False)
	def watch(self, path):
		self._watcher.addPath(path)
	def unwatch(self, path):
		self._watcher.removePath(path)

if PLATFORM == 'Windows':

	class DrivesFileSystem(FileSystem):

		scheme = 'drives://'

		def resolve(self, path):
			if not path:
				# Showing the list of all drives:
				return self.scheme
			if path in self._get_drives():
				return as_file_url(path + '\\')
			raise FileNotFoundError(path)
		def parent(self, path):
			return ''
		def iterdir(self, path):
			if path:
				raise FileNotFoundError(path)
			return self._get_drives()
		def isdir(self, path):
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

class Column:
	def get_str(cls, url):
		raise NotImplementedError()
	def get_sort_value(self, url, is_ascending):
		"""
		This method should generally be independent of is_ascending.
		When is_ascending is False, Qt simply reverses the sort order.
		However, we may sometimes want to change the sort order in a way other
		than a simple reversal when is_ascending is False. That's why this
		method receives is_ascending as a parameter.
		"""
		raise NotImplementedError()

class NameColumn(Column):

	name = 'Name'

	def __init__(self, fs=fman.fs):
		super().__init__()
		self._fs = fs
	def get_str(self, url):
		if re.match('/+', url):
			return '/'
		url = url.rstrip('/')
		try:
			return url[url.rindex('/')+1:]
		except ValueError:
			return url
	def get_sort_value(self, url, is_ascending):
		is_dir = self._fs.isdir(url)
		return is_dir ^ is_ascending, basename(url).lower()

class SizeColumn(Column):

	name = 'Size'

	def __init__(self, fs=fman.fs):
		super().__init__()
		self._fs = fs
	def get_str(self, url):
		if self._fs.isdir(url):
			return ''
		size_bytes = self._fs.getsize(url)
		if size_bytes is None:
			return ''
		units = ('%d bytes', '%d KB', '%.1f MB', '%.1f GB')
		if size_bytes <= 0:
			unit_index = 0
		else:
			unit_index = min(int(log(size_bytes, 1024)), len(units) - 1)
		unit = units[unit_index]
		base = 1024 ** unit_index
		return unit % (size_bytes / base)
	def get_sort_value(self, url, is_ascending):
		is_dir = self._fs.isdir(url)
		if is_dir:
			ord_ = ord if is_ascending else lambda c: -ord(c)
			minor = tuple(ord_(c) for c in basename(url).lower())
		else:
			minor = self._fs.getsize(url)
		return is_dir ^ is_ascending, minor

class LastModifiedColumn(Column):

	name = 'Modified'

	def __init__(self, fs=fman.fs):
		super().__init__()
		self._fs = fs
	def get_str(self, url):
		try:
			mtime = self._fs.getmtime(url)
		except OSError:
			return ''
		if mtime is None:
			return ''
		modified = datetime.fromtimestamp(mtime)
		return modified.strftime('%Y-%m-%d %H:%M')
	def get_sort_value(self, url, is_ascending):
		is_dir = self._fs.isdir(url)
		return is_dir ^ is_ascending, self._fs.getmtime(url)