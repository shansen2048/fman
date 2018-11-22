from fbs import path, SETTINGS
from fbs.resources import copy_with_filtering
from os import listdir
from os.path import exists
from shutil import rmtree
from subprocess import DEVNULL

import subprocess

def build_docker_image(name):
	build_dir = path('target/%s-docker-image' % name)
	if exists(build_dir):
		rmtree(build_dir)
	src_dir = path('src/build/docker/' + name)
	filter_ = [path(f) for f in SETTINGS['files_to_filter']]
	copy_with_filtering(src_dir, build_dir, files_to_filter=filter_)
	for p in SETTINGS['docker_images'][name].get('build_files', []):
		copy_with_filtering(path(p), build_dir, files_to_filter=filter_)
	img_path = _get_docker_path(name)
	subprocess.run(
		['docker', 'build', '--pull', '-t', img_path, build_dir], check=True
	)

def run_docker_image(name):
	args = ['docker', 'run', '-it']
	img_path = _get_docker_path(name)
	for item in _get_docker_mounts(img_path).items():
		args.append('-v')
		args.append('%s:%s' % item)
	args.append(img_path)
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