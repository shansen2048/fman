from collections import namedtuple
from core.os_ import is_arch
from core.util import filenotfounderror
from datetime import datetime
from fman import PLATFORM
from fman.fs import FileSystem
from fman.url import as_url, splitscheme
from io import UnsupportedOperation
from os.path import join, dirname
from pathlib import PurePosixPath, Path
from subprocess import Popen, PIPE, DEVNULL, CalledProcessError
from tempfile import TemporaryDirectory

import fman.fs
import os

if is_arch():
	bin_dir = '/usr/bin'
else:
	bin_dir = join(dirname(dirname(dirname(__file__))), 'bin', PLATFORM.lower())

_7ZIP_BINARY = join(bin_dir, '7za' + ('.exe' if PLATFORM == 'Windows' else ''))

del bin_dir

class ZipFileSystem(FileSystem):

	scheme = 'zip://'

	_7ZIP_WARNING = 1

	def __init__(self, fs=fman.fs):
		super().__init__()
		self._fs = fs

	def get_default_columns(self, path):
		return 'Name', 'Size', 'Modified'
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
		elif src_scheme == dst_scheme:
			# Guaranteed by fman's file system implementation:
			assert src_scheme == self.scheme
			with TemporaryDirectory() as tmp_dir:
				tmp_dst = join(as_url(tmp_dir), 'tmp')
				self.copy(src_url, tmp_dst)
				self.copy(tmp_dst, dst_url)
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
			src_scheme, src_path = splitscheme(src_url)
			if src_scheme == 'zip://':
				self.delete(src_path)
			else:
				self._fs.delete(src_url)
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
			raise filenotfounderror(path)
		else:
			with TemporaryDirectory() as tmp_dir:
				self._add_to_zip(tmp_dir, zip_path, path_in_zip)
	def delete(self, path):
		if not self.exists(path):
			raise filenotfounderror(path)
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
			raise filenotfounderror(self.scheme + path) from None
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
				url = '%s%s/%s' % (self.scheme, zip_path, path_in_zip)
				raise filenotfounderror(url)
			while file_info:
				yield file_info
				file_info = self._read_file_info(process.stdout)
		finally:
			self._close_7zip(process, terminate=True)
	def _raise_filenotfounderror_if_not_exists(self, zip_path):
		os.stat(zip_path)
	def _start_7zip(self, args, cwd=None):
		extra_kwargs = {}
		if PLATFORM == 'Windows':
			from subprocess import STARTF_USESHOWWINDOW, SW_HIDE, STARTUPINFO
			si = STARTUPINFO()
			si.dwFlags = STARTF_USESHOWWINDOW
			si.wShowWindow = SW_HIDE
			extra_kwargs['startupinfo'] = si
		return Popen(
			[_7ZIP_BINARY] + args,
			stdout=PIPE, stderr=DEVNULL, cwd=cwd, universal_newlines=True,
			**extra_kwargs
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
	def _run_7zip(self, args, cwd=None):
		process = self._start_7zip(args, cwd=cwd)
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
			return _FileInfo(path, is_dir, size, mtime)

_FileInfo = namedtuple('_FileInfo', ('path', 'is_dir', 'size_bytes', 'mtime'))