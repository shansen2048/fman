from collections import namedtuple
from datetime import datetime
from errno import ENOENT
from fman import PLATFORM
from fman.fs import delete, FileSystem
from fman.impl.trash import move_to_trash
from fman.impl.util.path import add_backslash_to_drive_if_missing
from fman.url import as_url, splitscheme
from io import UnsupportedOperation
from math import log
from os import remove
from os.path import isdir, getsize, getmtime, basename, samefile, join, dirname
from pathlib import Path, PurePosixPath
from PyQt5.QtCore import QFileSystemWatcher
from shutil import rmtree, copytree, move, copyfile, copystat
from subprocess import Popen, PIPE, DEVNULL, CalledProcessError
from tempfile import TemporaryDirectory

import fman.fs
import os
import re

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

	if PLATFORM == 'Windows':
		_7ZIP = join(dirname(__file__), '7za.exe')
	else:
		_7ZIP = join(dirname(__file__), '7za')

	_7ZIP_WARNING = 1

	def resolve(self, path):
		if '.zip' in path:
			# Return zip:// + path:
			return super().resolve(path)
		return as_url(path)
	def iterdir(self, path):
		zip_path, path_in_zip = self._split(path)
		already_yielded = set()
		for candidate in self._iter_names(zip_path, path_in_zip):
			while candidate:
				candidate_path = PurePosixPath(candidate)
				parent = str(candidate_path.parent)
				if parent == '.':
					parent = ''
				if parent == path_in_zip:
					name = candidate_path.name
					if name not in already_yielded:
						yield name
						already_yielded.add(name)
				candidate = parent
	def is_dir(self, path):
		try:
			zip_path, dir_path = self._split(path)
		except FileNotFoundError:
			return False
		if not dir_path:
			return Path(zip_path).exists()
		try:
			for info in self._iter_infos(zip_path, dir_path):
				if info.path == dir_path:
					return info.is_dir
				return True
		except FileNotFoundError:
			return False
		return False
	def exists(self, path):
		try:
			zip_path, path_in_zip = self._split(path)
		except FileNotFoundError:
			return False
		if not path_in_zip:
			return Path(zip_path).exists()
		try:
			next(iter(self._iter_infos(zip_path, path_in_zip)))
		except FileNotFoundError:
			return False
		return True
	def copy(self, src_url, dst_url):
		src_scheme, src_path = splitscheme(src_url)
		dst_scheme, dst_path = splitscheme(dst_url)
		if src_scheme == self.scheme and dst_scheme == 'file://':
			zip_path, path_in_zip = self._split(src_path)
			self._extract(zip_path, path_in_zip, dst_path)
		elif src_scheme == 'file://' and dst_scheme == self.scheme:
			zip_path, path_in_zip = self._split(dst_path)
			self._add_to_zip(src_path, zip_path, path_in_zip)
		else:
			raise UnsupportedOperation()
	def move(self, src_url, dst_url):
		src_scheme, src_path = splitscheme(src_url)
		dst_scheme, dst_path = splitscheme(dst_url)
		if src_scheme == dst_scheme:
			# Guaranteed by fman's file system implementation:
			assert src_scheme == self.scheme
			src_zip, src_pth_in_zip = self._split(src_path)
			dst_zip, dst_pth_in_zip = self._split(dst_path)
			if src_zip == dst_zip:
				with self._preserve_empty_parent(src_zip, src_pth_in_zip):
					self._run_7zip(
						['rn', src_zip, src_pth_in_zip, dst_pth_in_zip]
					)
			else:
				with TemporaryDirectory() as tmp_dir:
					tmp_dst = join(as_url(tmp_dir), 'tmp')
					self.copy(src_url, tmp_dst)
					self.move(tmp_dst, dst_url)
					self.delete(src_path)
		else:
			self.copy(src_url, dst_url)
			delete(src_url)
	def mkdir(self, path):
		if self.exists(path):
			raise FileExistsError(path)
		zip_path, path_in_zip = self._split(path)
		if not path_in_zip:
			# Run 7-Zip in an empty directory to create an empty archive:
			with TemporaryDirectory() as tmp_dir:
				name = PurePosixPath(zip_path).name
				self._run_7zip(['a', name], cwd=tmp_dir)
				Path(tmp_dir, name).rename(zip_path)
		elif not self.exists(str(PurePosixPath(path).parent)):
			raise FileNotFoundError(ENOENT, path)
		else:
			with TemporaryDirectory() as tmp_dir:
				self._add_to_zip(tmp_dir, zip_path, path_in_zip)
	def delete(self, path):
		if not self.exists(path):
			raise FileNotFoundError(path)
		zip_path, path_in_zip = self._split(path)
		with self._preserve_empty_parent(zip_path, path_in_zip):
			self._run_7zip(['d', zip_path, path_in_zip])
	def get_size_bytes(self, path):
		zip_path, dir_path = self._split(path)
		for info in self._iter_infos(zip_path, dir_path):
			if info.path == dir_path:
				return info.size_bytes
			# Is a directory:
			return None
	def get_modified_datetime(self, path):
		zip_path, dir_path = self._split(path)
		for info in self._iter_infos(zip_path, dir_path):
			if info.path == dir_path:
				return info.mtime
			# Is a directory:
			return None
	def _preserve_empty_parent(self, zip_path, path_in_zip):
		# 7-Zip deletes empty directories that remain after an operation. For
		# instance, when deleting the last file from a directory, or when moving
		# it out of the directory. We don't want this to happen. The present
		# method allows us to preserve the parent directory, even if empty:
		parent = str(PurePosixPath(path_in_zip).parent)
		parent_fullpath = zip_path + '/' + parent
		class CM:
			def __enter__(cm):
				if parent != '.':
					cm._parent_wasdir_before = self.is_dir(parent_fullpath)
				else:
					cm._parent_wasdir_before = False
			def __exit__(cm, exc_type, exc_val, exc_tb):
				if not exc_val:
					if cm._parent_wasdir_before:
						if not self.is_dir(parent_fullpath):
							self.makedirs(parent_fullpath)
		return CM()
	def _extract(self, zip_path, path_in_zip, dst_path):
		tmp_dir = TemporaryDirectory()
		try:
			args = ['x', zip_path, '-o' + tmp_dir.name]
			if path_in_zip:
				args.insert(2, path_in_zip)
			self._run_7zip(args)
			root = Path(tmp_dir.name, *path_in_zip.split('/'))
			root.rename(dst_path)
		finally:
			try:
				tmp_dir.cleanup()
			except FileNotFoundError:
				# This happens when path_in_zip = ''
				pass
	def _add_to_zip(self, src_path, zip_path, path_in_zip):
		if not path_in_zip:
			raise ValueError(
				'Must specify the destination path inside the archive'
			)
		with TemporaryDirectory() as tmp_dir:
			dest = Path(tmp_dir, *path_in_zip.split('/'))
			dest.parent.mkdir(parents=True, exist_ok=True)
			src = Path(src_path)
			dest.symlink_to(src, src.is_dir())
			args = ['a', zip_path, path_in_zip]
			if PLATFORM != 'Windows':
				args.insert(1, '-l')
			self._run_7zip(args, cwd=tmp_dir)
	def _split(self, path):
		suffix = '.zip'
		try:
			split_point = path.index(suffix) + len(suffix)
		except ValueError:
			raise FileNotFoundError('Not a .zip file: %r' % path) from None
		return path[:split_point], path[split_point:].lstrip('/')
	def _iter_names(self, zip_path, path_in_zip):
		for file_info in self._iter_infos(zip_path, path_in_zip):
			yield file_info.path
	def _iter_infos(self, zip_path, path_in_zip):
		self._raise_filenotfounderror_if_not_exists(zip_path)
		args = ['l', '-ba', '-slt', zip_path]
		if path_in_zip:
			args.append(path_in_zip)
		process = self._start_7zip(args)
		try:
			file_info = self._read_file_info(process.stdout)
			if not file_info:
				raise FileNotFoundError(zip_path + '/' + path_in_zip)
			while file_info:
				yield file_info
				file_info = self._read_file_info(process.stdout)
		finally:
			self._close_7zip(process, terminate=True)
	def _raise_filenotfounderror_if_not_exists(self, zip_path):
		os.stat(zip_path)
	def _start_7zip(self, args, **kwargs):
		return Popen(
			[self._7ZIP] + args,
			stdout=PIPE, stderr=DEVNULL, universal_newlines=True, **kwargs
		)
	def _close_7zip(self, process, terminate=False):
		try:
			if terminate:
				process.terminate()
				process.wait()
			else:
				exit_code = process.wait()
				if exit_code and exit_code != self._7ZIP_WARNING:
					raise CalledProcessError(exit_code, process.args)
		finally:
			process.stdout.close()
	def _run_7zip(self, args, **kwargs):
		process = self._start_7zip(args, **kwargs)
		self._close_7zip(process)
	def _read_file_info(self, stdout):
		path = size = mtime = None
		is_dir = False
		for line in stdout:
			line = line.rstrip('\n')
			if not line:
				break
			if line.startswith('Path = '):
				path = line[len('Path = '):].replace(os.sep, '/')
			elif line.startswith('Folder = '):
				folder = line[len('Folder = '):]
				is_dir = folder == '+'
			elif line.startswith('Size = '):
				size = int(line[len('Size = '):])
			elif line.startswith('Modified = '):
				mtime_str = line[len('Modified = '):]
				if mtime_str:
					mtime = datetime.strptime(mtime_str, '%Y-%m-%d %H:%M:%S')
		if path:
			return ZipInfo(path, is_dir, size, mtime)

ZipInfo = namedtuple('ZipInfo', ('path', 'is_dir', 'size_bytes', 'mtime'))

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
		size_bytes = self._fs.get_size_bytes(url)
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
			minor = self._fs.get_size_bytes(url)
		return is_dir ^ is_ascending, minor

class LastModifiedColumn(Column):

	name = 'Modified'

	def __init__(self, fs=fman.fs):
		super().__init__()
		self._fs = fs
	def get_str(self, url):
		try:
			mtime = self._fs.get_modified_datetime(url)
		except OSError:
			return ''
		if mtime is None:
			return ''
		return mtime.strftime('%Y-%m-%d %H:%M')
	def get_sort_value(self, url, is_ascending):
		is_dir = self._fs.is_dir(url)
		return is_dir ^ is_ascending, self._fs.get_modified_datetime(url)