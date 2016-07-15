from os import makedirs, readlink, symlink
from os.path import dirname, join, relpath, samefile, islink, isdir, basename, \
	isfile
from shutil import copy, copytree
from subprocess import Popen, STDOUT, CalledProcessError, check_output

import fnmatch
import os
import sys

PROJECT_DIR = dirname(__file__)

def path(relpath):
	return join(PROJECT_DIR, *relpath.split('/'))

def copy_with_filtering(
	src_dir_or_file, dest_dir, dict_, files_to_filter=None, exclude_files=None
):
	if exclude_files is None:
		exclude_files = []
	to_copy = _get_files_to_copy(src_dir_or_file, dest_dir, exclude_files)
	to_filter = _paths(files_to_filter)
	for src, dest in to_copy:
		makedirs(dirname(dest), exist_ok=True)
		if files_to_filter is None or src in to_filter:
			_copy_with_filtering(src, dest, dict_)
		else:
			copy(src, dest)

def _get_files_to_copy(src_dir_or_file, dest_dir, files_to_exclude):
	excludes = _paths(files_to_exclude)
	if isfile(src_dir_or_file) and src_dir_or_file not in excludes:
		yield src_dir_or_file, join(dest_dir, basename(src_dir_or_file))
	else:
		for (subdir, _, files) in os.walk(src_dir_or_file):
			dest_subdir = join(dest_dir, relpath(subdir, src_dir_or_file))
			for file_ in files:
				file_path = join(subdir, file_)
				if file_path in excludes:
					continue
				dest_path = join(dest_subdir, file_)
				yield file_path, dest_path

def _copy_with_filtering(
	src_file, dest_file, dict_, place_holder='${%s}', encoding='utf-8'
):
	replacements = []
	for key, value in dict_.items():
		old = (place_holder % key).encode(encoding)
		new = value.encode(encoding)
		replacements.append((old, new))
	with open(src_file, 'rb') as open_src_file:
		with open(dest_file, 'wb') as open_dest_file:
			for line in open_src_file:
				new_line = line
				for old, new in replacements:
					new_line = new_line.replace(old, new)
				open_dest_file.write(new_line)

class _paths:
	def __init__(self, paths):
		self.paths = paths
	def __contains__(self, item):
		return any(samefile(item, p) for p in self.paths)

def copy_framework(src_dir, dest_dir):
	assert basename(src_dir).endswith('.framework')
	name = basename(src_dir)[:-len('.framework')]
	version = basename(readlink(join(src_dir, 'Versions', 'Current')))
	files = [
		name, 'Resources', 'Versions/Current',
		'Versions/%s/%s' % (version, name), 'Versions/%s/Resources' % version
	]
	_copy_files(src_dir, dest_dir, files)

def _copy_files(src_dir, dest_dir, files):
	for file_ in files:
		src = join(src_dir, file_)
		dst = join(dest_dir, file_)
		makedirs(dirname(dst), exist_ok=True)
		if islink(src):
			symlink(readlink(src), dst)
		elif isdir(src):
			copytree(src, dst, symlinks=True)
		else:
			copy(src, dst, follow_symlinks=False)

def run(cmd, extra_env=None):
	if extra_env:
		env = dict(os.environ)
		env.update(extra_env)
	else:
		env = None
	process = Popen(cmd, env=env, stderr=STDOUT)
	process.wait()
	if process.returncode:
		raise CalledProcessError(process.returncode, cmd)

def unzip(zip, dest_dir):
	# Would actually prefer to use Python's ZipFile here, but it doesn't
	# preserve file permissions (in particular, executability). See:
	# https://bugs.python.org/issue15795
	run(['unzip', '-o', zip, '-d', dest_dir])

def glob_recursive(dir_, pattern):
	return [
		join(dirpath, f)
		for dirpath, _, files in os.walk(dir_)
		for f in fnmatch.filter(files, pattern)
	]

def get_rpath_references(so_path):
	result = []
	shared_libraries = \
		check_output(['otool', '-L', so_path], universal_newlines=True)
	for line in shared_libraries.split('\n'):
		rpath_prefix = '@rpath/'
		try:
			prefix_index = line.index(rpath_prefix)
		except ValueError:
			pass
		else:
			prefix = line[prefix_index:]
			result.append(prefix[:prefix.index(' ')])
	return result

def is_windows():
	return sys.platform in ('win32', 'cygwin')

def is_osx():
	return sys.platform == 'darwin'

def is_linux():
	return sys.platform.startswith('linux')

def get_canonical_os_name():
	if is_windows():
		return 'windows'
	if is_osx():
		return 'osx'
	if is_linux():
		return 'linux'
	raise ValueError('Unknown operating system.')