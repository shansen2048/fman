from datetime import datetime
from fman.url import splitscheme, as_file_url
from fman.impl.trash import move_to_trash
from math import log
from os import rename, remove
from os.path import isdir, getsize, getmtime, basename
from pathlib import Path
from PyQt5.QtCore import QFileSystemWatcher
from shutil import rmtree
from threading import Lock

class FileSystem:

	scheme = ''

	def __init__(self):
		self._file_changed_callbacks = {}
		self._file_changed_callbacks_lock = Lock()
	def notify_file_changed(self, path):
		for callback in self._file_changed_callbacks.get(path, []):
			callback(path)
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
	def listdir(self, path):
		return [as_file_url(child) for child in Path(path).iterdir()]
	def isdir(self, path):
		return isdir(path)
	def getsize(self, path):
		return getsize(path)
	def getmtime(self, path):
		return getmtime(path)
	def touch(self, path):
		Path(path).touch()
	def mkdir(self, path):
		Path(path).mkdir()
	def rename(self, old_path, new_path):
		rename(old_path, new_path)
	def move_to_trash(self, file_path):
		move_to_trash(file_path)
	def delete(self, path):
		if self.isdir(path):
			rmtree(path)
		else:
			remove(path)
	def resolve(self, path):
		return Path(path).resolve().as_posix()
	def watch(self, path):
		self._watcher.addPath(path)
	def unwatch(self, path):
		self._watcher.removePath(path)

class Column:
	def __init__(self, fs):
		self.fs = fs
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

	def get_str(self, url):
		return basename(splitscheme(url)[1])
	def get_sort_value(self, url, is_ascending):
		is_dir = self.fs.isdir(url)
		return is_dir ^ is_ascending, basename(url).lower()

class SizeColumn(Column):

	name = 'Size'

	def get_str(self, url):
		if self.fs.isdir(url):
			return ''
		size_bytes = self.fs.getsize(url)
		units = ('%d bytes', '%d KB', '%.1f MB', '%.1f GB')
		if size_bytes <= 0:
			unit_index = 0
		else:
			unit_index = min(int(log(size_bytes, 1024)), len(units) - 1)
		unit = units[unit_index]
		base = 1024 ** unit_index
		return unit % (size_bytes / base)
	def get_sort_value(self, url, is_ascending):
		is_dir = self.fs.isdir(url)
		if is_dir:
			ord_ = ord if is_ascending else lambda c: -ord(c)
			minor = tuple(ord_(c) for c in basename(url).lower())
		else:
			minor = self.fs.getsize(url)
		return is_dir ^ is_ascending, minor

class LastModifiedColumn(Column):

	name = 'Modified'

	def get_str(self, url):
		try:
			modified = datetime.fromtimestamp(self.fs.getmtime(url))
		except OSError:
			return ''
		return modified.strftime('%Y-%m-%d %H:%M')
	def get_sort_value(self, url, is_ascending):
		is_dir = self.fs.isdir(url)
		return is_dir ^ is_ascending, self.fs.getmtime(url)