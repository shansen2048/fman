from importlib import import_module
from os import makedirs, readlink, symlink
from os.path import dirname, join, relpath, samefile, islink, isdir, basename, \
	isfile, pardir, exists, normpath
from shutil import copy, copytree
from subprocess import Popen, STDOUT, CalledProcessError

import json
import os
import re
import sys

PROJECT_DIR = join(dirname(__file__), pardir)

# We cannot have this dict in the same file as __main__.
# See: http://stackoverflow.com/q/38702175/1839209
OPTIONS = {}

def path(relpath):
	return normpath(join(PROJECT_DIR, *relpath.split('/')))

def generate_resources(dest_dir=path('target/resources')):
	copy_with_filtering(path('src/main/resources/base'), dest_dir)
	os_resources_dir = path('src/main/resources/' + get_canonical_os_name())
	if exists(os_resources_dir):
		copy_with_filtering(os_resources_dir, dest_dir)

def copy_with_filtering(
	src_dir_or_file, dest_dir, replacements=None, files_to_filter=None
):
	if replacements is None:
		replacements = _read_filter()
	if files_to_filter is None:
		files_to_filter = OPTIONS['files_to_filter']
	to_copy = _get_files_to_copy(src_dir_or_file, dest_dir)
	to_filter = _paths(files_to_filter)
	for src, dest in to_copy:
		makedirs(dirname(dest), exist_ok=True)
		if files_to_filter is None or src in to_filter:
			_copy_with_filtering(src, dest, replacements)
		else:
			copy(src, dest)

def _read_filter():
	filter_type = 'release' if OPTIONS['release'] else 'local'
	filter_path = path('src/main/filters/filter-%s.json' % filter_type)
	with open(filter_path, 'r') as f:
		result = json.load(f)
	result['version'] = OPTIONS['version']
	return result

def _get_files_to_copy(src_dir_or_file, dest_dir):
	if isfile(src_dir_or_file):
		yield src_dir_or_file, join(dest_dir, basename(src_dir_or_file))
	else:
		for (subdir, _, files) in os.walk(src_dir_or_file):
			dest_subdir = join(dest_dir, relpath(subdir, src_dir_or_file))
			for file_ in files:
				file_path = join(subdir, file_)
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

def copy_python_library(name, dest_dir):
	library = import_module(name)
	is_package = re.match(r'^__init__\.pyc?$', basename(library.__file__))
	if is_package:
		copytree(dirname(library.__file__), dest_dir)
	else:
		copy(library.__file__, dest_dir)

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