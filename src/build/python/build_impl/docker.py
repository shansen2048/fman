from fbs import path, SETTINGS
from fbs.resources import copy_with_filtering
from os import listdir
from os.path import exists, join
from shutil import rmtree, copy, copytree
from subprocess import DEVNULL

import subprocess
import sys

def build_docker_image(
	name, extra_files=None, files_to_filter=None, replacements=None
):
	if extra_files is None:
		extra_files = []
	build_dir = path('target/%s-docker-image' % name)
	src_dir = path('src/build/docker/' + name)

	if exists(build_dir):
		rmtree(build_dir)

	copy_with_filtering(src_dir, build_dir, replacements, files_to_filter)
	for p in (
		'conf/ssh/id_rsa.pub', 'conf/linux/private.gpg-key',
		'conf/linux/public.gpg-key'
	):
		copy(path(p), build_dir)
	copytree(path('requirements'), join(build_dir, 'requirements'))
	for f in extra_files:
		copy(f, build_dir)
	img_path = _get_docker_path(name)
	subprocess.run(
		['docker', 'build', '--pull', '-t', img_path, build_dir], check=True
	)

def run_docker_image(name, extra_args=None):
	if extra_args is None:
		extra_args = sys.argv[2:]
	args = ['docker', 'run', '-it']
	img_path = _get_docker_path(name)
	for item in _get_docker_mounts(img_path).items():
		args.append('-v')
		args.append('%s:%s' % item)
	args.append(img_path)
	args.extend(extra_args)
	subprocess.run(args)

def _get_docker_path(image_name):
	prefix = SETTINGS['app_name'].replace(' ', '_').lower()
	suffix = image_name.lower()
	return prefix + '/' + suffix

def _get_docker_mounts(img_path):
	target_subdir = path('target/' + img_path.split('/')[1])
	result = {
		target_subdir: '/root/dev/fman/target'
	}
	for file_name in listdir(path('.')):
		file_path = path(file_name)
		if _is_in_gitignore(file_path):
			continue
		result[file_path] = '/root/dev/fman/' + file_name
	return result

def _is_in_gitignore(file_path):
	process = subprocess.run(['git', 'check-ignore', file_path], stdout=DEVNULL)
	return not process.returncode