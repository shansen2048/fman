from datetime import datetime
from fman.impl.trash import move_to_trash
from fman.util import Signal, listdir_absolute
from math import log
from os import rename, remove
from os.path import isdir, getsize, getmtime, basename
from pathlib import Path
from PyQt5.QtCore import QFileSystemWatcher
from shutil import rmtree

class FileSystem:
	def __init__(self):
		self.file_changed = Signal()
	def broadcast_file_changed(self, path):
		self.file_changed.emit(path)

class DefaultFileSystem(FileSystem):
	def __init__(self):
		super().__init__()
		self._watcher = QFileSystemWatcher()
		self._watcher.directoryChanged.connect(self.broadcast_file_changed)
		self._watcher.fileChanged.connect(self.broadcast_file_changed)
	def exists(self, path):
		return Path(path).exists()
	def listdir(self, path):
		return listdir_absolute(path)
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
	def watch(self, path):
		self._watcher.addPath(path)
	def unwatch(self, path):
		self._watcher.removePath(path)

class Column:
	def __init__(self, fs):
		self.fs = fs
	def get_str(cls, file_path):
		raise NotImplementedError()
	def get_sort_value(self, file_path, is_ascending):
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

	def get_str(self, file_path):
		return basename(file_path)
	def get_sort_value(self, file_path, is_ascending):
		is_dir = self.fs.isdir(file_path)
		return is_dir ^ is_ascending, basename(file_path).lower()

class SizeColumn(Column):

	name = 'Size'

	def get_str(self, file_path):
		if self.fs.isdir(file_path):
			return ''
		size_bytes = self.fs.getsize(file_path)
		units = ('%d bytes', '%d KB', '%.1f MB', '%.1f GB')
		if size_bytes <= 0:
			unit_index = 0
		else:
			unit_index = min(int(log(size_bytes, 1024)), len(units) - 1)
		unit = units[unit_index]
		base = 1024 ** unit_index
		return unit % (size_bytes / base)
	def get_sort_value(self, file_path, is_ascending):
		is_dir = self.fs.isdir(file_path)
		if is_dir:
			ord_ = ord if is_ascending else lambda c: -ord(c)
			minor = tuple(ord_(c) for c in basename(file_path).lower())
		else:
			minor = self.fs.getsize(file_path)
		return is_dir ^ is_ascending, minor

class LastModifiedColumn(Column):

	name = 'Modified'

	def get_str(self, file_path):
		try:
			modified = datetime.fromtimestamp(self.fs.getmtime(file_path))
		except OSError:
			return ''
		return modified.strftime('%Y-%m-%d %H:%M')
	def get_sort_value(self, file_path, is_ascending):
		is_dir = self.fs.isdir(file_path)
		return is_dir ^ is_ascending, self.fs.getmtime(file_path)