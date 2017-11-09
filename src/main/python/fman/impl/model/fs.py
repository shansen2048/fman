from datetime import datetime
from errno import ENOENT
from fman import PLATFORM
from fman.impl.util.url import resolve
from fman.url import as_url, splitscheme
from fman.impl.trash import move_to_trash
from fman.impl.util.path import add_backslash_to_drive_if_missing, parent
from io import UnsupportedOperation
from math import log
from os import remove
from os.path import isdir, getsize, getmtime, basename, samefile, relpath
from pathlib import Path, PurePosixPath
from PyQt5.QtCore import QFileSystemWatcher
from shutil import rmtree, copytree, move, copyfile, copystat
from tempfile import TemporaryDirectory
from threading import Lock
from zipfile import ZipFile

import fman.fs
import os
import posixpath
import re

class FileSystem:

	scheme = ''

	def __init__(self):
		self._file_changed_callbacks = {}
		self._file_changed_callbacks_lock = Lock()
	def iterdir(self, path):
		raise NotImplementedError()
	def resolve(self, path):
		return resolve(self.scheme + path)
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
			if not exist_ok or not self.is_dir(path):
				raise
		except OSError as e:
			if e.errno != ENOENT:
				raise
			self.makedirs(parent(path))
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
	def is_dir(self, path):
		return isdir(path)
	def getsize(self, path):
		return getsize(path)
	def getmtime(self, path):
		return getmtime(path)
	def touch(self, path):
		Path(path).touch()
	def mkdir(self, path):
		Path(path).mkdir()
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
		path = add_backslash_to_drive_if_missing(path)
		return as_url(Path(path).resolve())
	def samefile(self, f1, f2):
		return samefile(f1, f2)
	def copy(self, src_url, dst_url):
		src_path, dst_path = self._get_src_dst_path(src_url, dst_url)
		if self.is_dir(src_path):
			copytree(src_path, dst_path, symlinks=True)
		else:
			copyfile(src_path, dst_path, follow_symlinks=False)
			copystat(src_path, dst_path, follow_symlinks=False)
	def watch(self, path):
		self._watcher.addPath(path)
	def unwatch(self, path):
		self._watcher.removePath(path)
	def _get_src_dst_path(self, src_url, dst_url):
		src_scheme, src_path = splitscheme(src_url)
		dst_scheme, dst_path = splitscheme(dst_url)
		if src_scheme != self.scheme or dst_scheme != self.scheme:
			raise UnsupportedOperation()
		return src_path, dst_path

if PLATFORM == 'Windows':

	class DrivesFileSystem(FileSystem):

		scheme = 'drives://'

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

class ZipFileSystem(FileSystem):

	scheme = 'zip://'

	def iterdir(self, path):
		zip_path, dir_path = self._split(path)
		with ZipFile(zip_path) as zipfile:
			already_yielded = set()
			for candidate in zipfile.namelist():
				while candidate:
					candidate_path = PurePosixPath(candidate)
					parent = str(candidate_path.parent)
					if parent == '.':
						parent = ''
					if parent == dir_path:
						name = candidate_path.name
						if name not in already_yielded:
							yield name
							already_yielded.add(name)
					candidate = parent
	def resolve(self, path):
		if '.zip' in path:
			# Return zip:// + path:
			return super().resolve(path)
		return as_url(path)
	def is_dir(self, path):
		try:
			zip_path, dir_path = self._split(path)
		except FileNotFoundError:
			return False
		if not dir_path:
			return True
		if not dir_path.endswith('/'):
			dir_path += '/'
		with ZipFile(zip_path) as zipfile:
			for entry in zipfile.namelist():
				if entry.startswith(dir_path):
					return True
		return False
	def exists(self, path):
		try:
			zip_path, path_in_zip = self._split(path)
		except FileNotFoundError:
			return False
		if not path_in_zip:
			return True
		with ZipFile(zip_path) as zipfile:
			for entry in zipfile.namelist():
				if self._contains(path_in_zip, entry):
					return True
		return False
	def copy(self, src_url, dst_url):
		src_scheme, src_path = splitscheme(src_url)
		dst_scheme, dst_path = splitscheme(dst_url)
		if src_scheme == self.scheme and dst_scheme == 'file://':
			zip_path, path_in_zip = self._split(src_path)
			self._extract(zip_path, path_in_zip, dst_path)
		elif src_scheme == 'file://' and dst_scheme == self.scheme:
			zip_path, path_in_zip = self._split(dst_path)
			with ZipFile(zip_path, 'a') as zipfile:
				if isdir(src_path):
					for dirpath, dirnames, filenames in os.walk(src_path):
						for file_name in dirnames + filenames:
							file_path = os.path.join(dirpath, file_name)
							rel_path = relpath(file_path, src_path)
							zipfile.write(
								file_path,
								'/'.join([path_in_zip] + rel_path.split(os.sep))
							)
				else:
					zipfile.write(src_path, path_in_zip)
		else:
			raise UnsupportedOperation()
	def mkdir(self, path):
		if self.exists(path):
			raise FileExistsError(path)
		if path and not self.exists(str(PurePosixPath(path).parent)):
			raise FileNotFoundError(ENOENT, path)
		zip_path, path_in_zip = self._split(path)
		with ZipFile(zip_path, 'a') as zip_file:
			with TemporaryDirectory() as tmp_dir:
				zip_file.write(tmp_dir, path_in_zip)
	def _extract(self, zip_path, path_in_zip, dst_path):
		found = False
		with ZipFile(zip_path) as zipfile:
			# Python's ZipFile#extract nests files in subdirectories.
			# Eg. #extract(a/b.txt, /tmp) places at /tmp/a/b.txt.
			# But we need /tmp/b.txt. To achieve this, extract to a temporary
			# directory, then move files:
			with TemporaryDirectory() as tmp_dir:
				for entry in zipfile.namelist():
					if self._contains(path_in_zip, entry):
						found = True
						zipfile.extract(entry, tmp_dir)
				root = Path(tmp_dir, *path_in_zip.split('/'))
				if root.is_dir():
					for path in root.iterdir():
						path.rename(Path(dst_path, path.name))
				else:
					root.rename(dst_path)
		if not found:
			raise FileNotFoundError()
	def _contains(self, parent, child):
		return not parent or child == parent or child.startswith(parent + '/')
	def _relpath(self, target, base):
		return posixpath.relpath(target, start=base)
	def _split(self, path):
		suffix = '.zip'
		try:
			split_point = path.index(suffix) + len(suffix)
		except ValueError:
			raise FileNotFoundError('Not a .zip file: %r' % path) from None
		return path[:split_point], path[split_point:].lstrip('/')

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
		is_dir = self._fs.is_dir(url)
		return is_dir ^ is_ascending, basename(url).lower()

class SizeColumn(Column):

	name = 'Size'

	def __init__(self, fs=fman.fs):
		super().__init__()
		self._fs = fs
	def get_str(self, url):
		if self._fs.is_dir(url):
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
		is_dir = self._fs.is_dir(url)
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
		is_dir = self._fs.is_dir(url)
		return is_dir ^ is_ascending, self._fs.getmtime(url)