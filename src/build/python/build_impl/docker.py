from fbs import path
from fbs.resources import copy_with_filtering
from os import makedirs, listdir
from os.path import exists, isdir, join
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
	image_name = 'fman/' + name
	cache_dir = path('cache/' + name)

	if exists(build_dir):
		rmtree(build_dir)
	if isdir(cache_dir):
		subprocess.run(['sudo', 'rm', '-rf', cache_dir])

	copy_with_filtering(src_dir, build_dir, replacements, files_to_filter)
	for p in (
		'conf/ssh/id_rsa.pub', 'conf/linux/private.gpg-key',
		'conf/linux/public.gpg-key'
	):
		copy(path(p), build_dir)
	copytree(path('requirements'), join(build_dir, 'requirements'))
	for f in extra_files:
		copy(f, build_dir)
	subprocess.run(
		['docker', 'build', '--pull', '-t', image_name, build_dir], check=True
	)
	makedirs(cache_dir, exist_ok=True)

def run_docker_image(image_name, cache_dir, extra_args=None):
	if extra_args is None:
		extra_args = sys.argv[2:]
	args = ['docker', 'run', '-it']
	for item in _get_docker_mounts(image_name, cache_dir).items():
		args.append('-v')
		args.append('%s:%s' % item)
	args.append(image_name)
	args.extend(extra_args)
	subprocess.run(args)

def _get_docker_mounts(image_name, cache_dir):
	target_subdir = path('target/' + image_name.split('/')[1])
	result = {
		target_subdir: '/root/dev/fman/target',
		join(cache_dir, 'cache'): '/root/dev/fman/cache'
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