from fbs.conf import SETTINGS, path
from fbs.platform import is_windows, is_mac, is_linux
from glob import glob
from importlib import import_module
from os import makedirs, readlink, symlink, remove
from os.path import dirname, join, relpath, islink, isdir, basename, isfile, \
	exists, splitext
from pathlib import Path
from shutil import copy, copytree, copymode
from subprocess import Popen, STDOUT, CalledProcessError, check_output
from time import time

import json
import os
import re
import sys

_ALL_OSS = {'mac', 'windows', 'linux'}

def read_filter():
	with open(path('src/main/filters/filter-local.json'), 'r') as f:
		result = json.load(f)
	if SETTINGS['release']:
		with open(path('src/main/filters/filter-release.json'), 'r') as f:
			result.update(json.load(f))
	return result

def generate_resources(dest_dir=None, dest_dir_for_base=None, exclude=None):
	if dest_dir is None:
		# Set this default here instead of in the function definition
		# (`def generate_resources(dest_dir=path(...) ...)`) because we can't
		# call path(...) at the module level.
		path('target/resources')
	if dest_dir_for_base is None:
		dest_dir_for_base = dest_dir
	if exclude is None:
		exclude = []
	exclude = exclude + _get_dirs_to_exclude_from_core_plugin()
	copy_with_filtering(
		path('src/main/resources/base'), dest_dir_for_base, exclude=exclude
	)
	os_resources_dir = path('src/main/resources/' + get_canonical_os_name())
	if exists(os_resources_dir):
		copy_with_filtering(os_resources_dir, dest_dir, exclude=exclude)

def _get_dirs_to_exclude_from_core_plugin():
	other_oss = set(_ALL_OSS)
	other_oss.remove(get_canonical_os_name())
	core_bin = 'src/main/resources/base/Plugins/Core/bin'
	return [path(core_bin) + '/' + to_exclude for to_exclude in other_oss]

def copy_with_filtering(
	src_dir_or_file, dest_dir, replacements=None, files_to_filter=None,
	exclude=None
):
	if replacements is None:
		replacements = SETTINGS
	if files_to_filter is None:
		files_to_filter = SETTINGS['files_to_filter']
	if exclude is None:
		exclude = []
	to_copy = _get_files_to_copy(src_dir_or_file, dest_dir, exclude)
	to_filter = _paths(files_to_filter)
	for src, dest in to_copy:
		makedirs(dirname(dest), exist_ok=True)
		if files_to_filter is None or src in to_filter:
			_copy_with_filtering(src, dest, replacements)
		else:
			copy(src, dest)

def _get_files_to_copy(src_dir_or_file, dest_dir, exclude):
	excludes = _paths(exclude)
	if isfile(src_dir_or_file) and src_dir_or_file not in excludes:
		yield src_dir_or_file, join(dest_dir, basename(src_dir_or_file))
	else:
		for (subdir, _, files) in os.walk(src_dir_or_file):
			dest_subdir = join(dest_dir, relpath(subdir, src_dir_or_file))
			for file_ in files:
				file_path = join(subdir, file_)
				dest_path = join(dest_subdir, file_)
				if file_path not in excludes:
					yield file_path, dest_path

def _copy_with_filtering(
	src_file, dest_file, dict_, place_holder='${%s}', encoding='utf-8'
):
	replacements = []
	for key, value in dict_.items():
		old = (place_holder % key).encode(encoding)
		new = str(value).encode(encoding)
		replacements.append((old, new))
	with open(src_file, 'rb') as open_src_file:
		with open(dest_file, 'wb') as open_dest_file:
			for line in open_src_file:
				new_line = line
				for old, new in replacements:
					new_line = new_line.replace(old, new)
				open_dest_file.write(new_line)
		copymode(src_file, dest_file)

class _paths:
	def __init__(self, paths):
		self._paths = [Path(p).resolve() for p in paths]
	def __contains__(self, item):
		item = Path(item).resolve()
		for p in self._paths:
			if p.samefile(item) or p in item.parents:
				return True
		return False

def replace_in_files(dir_, string, replacement):
	for subdir, _, files in os.walk(dir_):
		for file_ in files:
			ext = splitext(file_)[1]
			if ext in (
				'.exe', '.lib', '.dll', '.pyc', '.dmp', '.cer', '.pfx', '.idb',
				'.dblite', '.avi', '.bmp', '.msi', '.ico', '.pdb', '.res', '.rc'
			):
				continue
			f_path = join(subdir, file_)
			try:
				replace_in_file(f_path, string, replacement, check_found=False)
			except UnicodeDecodeError:
				pass

def replace_in_file(path, string, replacement, check_found=True):
	with open(path, 'r') as f:
		contents = f.read()
	if check_found:
		assert string in contents, contents
	with open(path, 'w') as f:
		f.write(contents.replace(string, replacement))

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

def remove_if_exists(file_path):
	try:
		remove(file_path)
	except FileNotFoundError:
		pass

def run_pyinstaller(extra_args=None):
	if extra_args is None:
		extra_args = []
	cmdline = [
		'pyinstaller',
		'--name', 'fman',
		'--noupx'
	] + extra_args + [
		'--distpath', path('target'),
		'--specpath', path('target/build'),
		'--workpath', path('target/build'),
		SETTINGS['main_module']
	]
	run(cmdline)

def copy_python_library(name, dest_dir):
	library = import_module(name)
	is_package = re.match(r'^__init__\.pyc?$', basename(library.__file__))
	if is_package:
		package_dir = dirname(library.__file__)
		copytree(package_dir, join(dest_dir, basename(package_dir)))
	else:
		copy(library.__file__, dest_dir)

def run(cmd, extra_env=None, check_result=True, cwd=None):
	if extra_env:
		env = dict(os.environ)
		env.update(extra_env)
	else:
		env = None
	process = Popen(cmd, env=env, stderr=STDOUT, cwd=cwd)
	process.wait()
	if check_result and process.returncode:
		raise CalledProcessError(process.returncode, cmd)

def get_canonical_os_name():
	if is_windows():
		return 'windows'
	if is_mac():
		return 'mac'
	if is_linux():
		return 'linux'
	raise ValueError('Unknown operating system.')

def get_icons():
	result = {}
	for icons_dir in (
		'src/main/icons/base', 'src/main/icons/' + get_canonical_os_name()
	):
		for icon_path in glob(path(icons_dir + '/*.png')):
			size = int(splitext(basename(icon_path))[0])
			result[size] = icon_path
	return list(result.items())

def upload_file(f, dest_dir):
	print('Uploading %s...' % basename(f))
	dest_path = get_path_on_server(dest_dir)
	if SETTINGS['release']:
		run([
			'rsync', '-ravz', '-e', 'ssh -i ' + SETTINGS['ssh_key'],
			f, SETTINGS['server_user'] + ':' + dest_path
		])
	else:
		if isdir(f):
			copytree(f, join(dest_dir, basename(f)))
		else:
			copy(f, dest_path)

def get_path_on_server(file_path):
	if file_path.startswith('/'):
		return file_path
	if SETTINGS['release']:
		staticfiles_dir = SETTINGS['server_media_dir']
	else:
		staticfiles_dir = SETTINGS['local_media_dir']
	return join(staticfiles_dir, file_path)

def run_on_server(command):
	if SETTINGS['release']:
		return check_output_decode([
			'ssh', '-i', SETTINGS['ssh_key'], SETTINGS['server_user'], command
		])
	else:
		return check_output_decode(command, shell=True)

def check_output_decode(*args, **kwargs):
	return check_output(*args, **kwargs).decode(sys.stdout.encoding)

def upload_installer_to_aws(installer_name):
	assert SETTINGS['release']
	src_path = path('target/' + installer_name)
	upload_to_s3(src_path, installer_name)
	version_dest_path = '%s/%s' % (SETTINGS['version'], installer_name)
	upload_to_s3(src_path, version_dest_path)

def git(cmd, *args):
	run(['git', cmd] + list(args))

def upload_to_s3(src_path, dest_path):
	import boto3
	s3 = boto3.resource('s3', **_get_aws_credentials())
	s3.Bucket(SETTINGS['aws_bucket']).upload_file(
		src_path, dest_path, ExtraArgs={'ACL': 'public-read'}
	)

def create_cloudfront_invalidation(items):
	import boto3
	cloudfront = boto3.client('cloudfront', **_get_aws_credentials())
	cloudfront.create_invalidation(
		DistributionId=SETTINGS['aws_distribution_id'],
		InvalidationBatch={
			'Paths': {
				'Quantity': len(items),
				'Items': items
			},
			'CallerReference': str(int(time()))
		}
	)

def _get_aws_credentials():
	return {
		'aws_access_key_id': SETTINGS['aws_access_key_id'],
		'aws_secret_access_key': SETTINGS['aws_secret_access_key']
	}