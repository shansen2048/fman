from fbs.conf import SETTINGS, path
from fbs.platform import is_windows, is_mac, is_linux
from glob import glob
from importlib import import_module
from os import makedirs, readlink, symlink, remove
from os.path import dirname, join, islink, isdir, basename, splitext
from shutil import copy, copytree
from subprocess import run, check_output
from time import time

import re
import sys

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

def copy_python_library(name, dest_dir):
	library = import_module(name)
	is_package = re.match(r'^__init__\.pyc?$', basename(library.__file__))
	if is_package:
		package_dir = dirname(library.__file__)
		copytree(package_dir, join(dest_dir, basename(package_dir)))
	else:
		copy(library.__file__, dest_dir)

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
		], check=True)
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
	run(['git', cmd] + list(args), check=True)

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