from fbs import path, SETTINGS
from fbs.resources import copy_with_filtering
from gitignore_parser import parse_gitignore
from os import listdir
from os.path import exists
from shutil import rmtree

import subprocess

def build_docker_image(name):
	build_dir = path('target/%s-docker-image' % name)
	if exists(build_dir):
		rmtree(build_dir)
	src_dir = path('src/build/docker/' + name)
	filter_ = [path(f) for f in SETTINGS['files_to_filter']]
	copy_with_filtering(src_dir, build_dir, files_to_filter=filter_)
	for p in _get_settings(name).get('build_files', []):
		copy_with_filtering(path(p), build_dir, files_to_filter=filter_)
	subprocess.run(
		['docker', 'build', '--pull', '-t', _get_docker_id(name), build_dir],
		check=True
	)

def run_docker_image(name):
	args = ['docker', 'run', '-it']
	for item in _get_docker_mounts(name).items():
		args.extend(['-v', '%s:%s' % item])
	args.append(_get_docker_id(name))
	subprocess.run(args)

def _get_docker_id(name):
	prefix = SETTINGS['app_name'].replace(' ', '_').lower()
	suffix = name.lower()
	return prefix + '/' + suffix

def _get_docker_mounts(name):
	result = {'target/' + name.lower(): 'target'}
	is_in_gitignore = parse_gitignore(path('.gitignore'))
	for file_name in listdir(path('.')):
		if is_in_gitignore(path(file_name)):
			continue
		result[file_name] = file_name
	path_in_docker = lambda p: '/root/%s/%s' % (name, p)
	return {path(src): path_in_docker(dest) for src, dest in result.items()}

def _get_settings(name):
	return SETTINGS['docker_images'][name]