from os import makedirs
from os.path import dirname, join, relpath, samefile
from shutil import copy
from subprocess import Popen, STDOUT, CalledProcessError

import json
import os

PROJECT_DIR = dirname(__file__)

def path(relpath):
	return join(PROJECT_DIR, *relpath.split('/'))

def copy_with_filtering(
	src_dir, dest_dir, exclude_files, filter_files, filter_path
):
	if filter_path:
		filter_path = path(filter_path)
	for (subdir, _, files) in os.walk(src_dir):
		dest_subdir = join(dest_dir, relpath(subdir, src_dir))
		makedirs(dest_subdir, exist_ok=True)
		for file_ in files:
			file_path = join(subdir, file_)
			if file_path in _paths(exclude_files):
				continue
			dest_path = join(dest_subdir, file_)
			if filter_path and file_path in _paths(filter_files):
				_copy_json_with_filtering(file_path, filter_path, dest_path)
			else:
				copy(file_path, dest_path)

class _paths:
	def __init__(self, paths):
		self.paths = paths
	def __contains__(self, item):
		return any(samefile(item, path(p)) for p in self.paths)

def _copy_json_with_filtering(json_file, filter_path, dest_path):
	with open(json_file, 'r') as f:
		data = json.load(f)
	with open(filter_path, 'r') as f:
		filter_ = json.load(f)
	data.update(filter_)
	with open(dest_path, 'w') as f:
		json.dump(data, f, indent='\t')

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