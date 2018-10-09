from fbs import path
from os import makedirs, listdir
from os.path import exists, isdir, join
from shutil import rmtree, copytree, copy
from subprocess import DEVNULL

import subprocess
import sys

def build_docker_image(name, python_executable):
	build_dir = path('target/%s-docker-image' % name)
	src_dir = path('src/build/docker/' + name)
	image_name = 'fman/' + name
	cache_dir = path('cache/' + name)
	requirements_txt = name + '.txt'

	if exists(build_dir):
		rmtree(build_dir)
	if isdir(cache_dir):
		subprocess.run(['sudo', 'rm', '-rf', cache_dir])

	copytree(src_dir, build_dir)
	copy(path('conf/ssh/id_rsa'), build_dir)
	copy(path('conf/ssh/id_rsa.pub'), build_dir)
	subprocess.run(
		['docker', 'build', '--pull', '-t', image_name, build_dir], check=True
	)
	makedirs(cache_dir, exist_ok=True)
	run_docker_image(image_name, cache_dir, ['/bin/bash', '-c',
	   python_executable + ' -m venv venv && '
	   'source venv/bin/activate && '
	   'python -m pip install -r requirements/' + requirements_txt
	])

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
		join(cache_dir, 'venv'): '/root/dev/fman/venv'
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