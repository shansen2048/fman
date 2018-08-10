from os.path import dirname, join
import sys
sys.path.append(join(dirname(__file__), *'src/build/python'.split('/')))

from build_impl import git, create_cloudfront_invalidation, \
	record_release_on_server
from fbs import path, activate_profile, SETTINGS
from fbs.builtin_commands import clean, installer
from fbs.cmdline import command
from fbs.platform import is_windows, is_mac, is_linux, is_ubuntu, is_arch_linux
from os import listdir, makedirs
from os.path import join, isdir, dirname, exists
from shutil import copytree, copy, rmtree
from subprocess import DEVNULL

import fbs.cmdline
import re
import subprocess
import sys

if is_windows():
	from build_impl.windows import exe, installer, sign_exe, sign_installer, \
		add_installer_manifest, upload
elif is_mac():
	from build_impl.mac import app, sign_app, sign_installer, upload, \
		create_autoupdate_files
elif is_linux():
	if is_ubuntu():
		from build_impl.ubuntu import exe, deb, upload
	elif is_arch_linux():
		from build_impl.arch import exe, pkg, sign_pkg, repo, pkgbuild, upload
	else:
		raise NotImplementedError()

@command
def publish():
	if is_windows():
		exe()
		sign_exe()
		installer()
		add_installer_manifest()
		sign_installer()
		upload()
	elif is_mac():
		app()
		sign_app()
		installer()
		sign_installer()
		create_autoupdate_files()
		upload()
	elif is_linux():
		if is_ubuntu():
			exe()
			deb()
			upload()
		elif is_arch_linux():
			exe()
			pkg()
			sign_pkg()
			repo()
			pkgbuild()
			upload()
		else:
			raise NotImplementedError()
	else:
		raise ValueError('Unknown operating system.')

@command
def release():
	clean()
	activate_profile('release')
	version = SETTINGS['version']
	if version.endswith(snapshot_suffix):
		release_version = version[:-len(snapshot_suffix)]
		print('Releasing version %s' % release_version)
		next_version = _prompt_for_next_version(release_version)
		revision_before = git('rev-parse', 'HEAD').rstrip()
		settings_path = path('src/build/settings/base.json')
		_commit_version(
			settings_path, release_version,
			'Set version number for release ' + release_version
		)
		try:
			SETTINGS['version'] = release_version
			publish()
			release_tag = 'v' + release_version
			git('tag', release_tag)
			try:
				_commit_version(
					settings_path, next_version + snapshot_suffix,
					'Bump version for next development iteration'
				)
				git('push', '-u', 'origin', 'master')
				try:
					git('push', 'origin', release_tag)
					try:
						git('checkout', release_tag)
						print(
							'\nDone. Run\n\n'
							'    git pull\n'
							'    git checkout %s\n'
							'    python build.py release\n'
							'    git checkout master\n\n'
							'on the other OSs now, then come back here and do:'
							'\n\n'
							'    python build.py post_release\n'
							% release_tag
						)
					except:
						git('push', '--delete', 'origin', release_tag)
						raise
				except:
					git('revert', '--no-edit', revision_before + '..HEAD' )
					git('push', '-u', 'origin', 'master')
					revision_before = git('rev-parse', 'HEAD').rstrip()
					raise
			except:
				git('tag', '-d', release_tag)
				raise
		except:
			git('reset', revision_before)
			_replace_in_json(settings_path, 'version', version)
			raise
	else:
		publish()

snapshot_suffix = '-SNAPSHOT'

@command
def post_release():
	activate_profile('release')
	version = SETTINGS['version']
	assert not version.endswith(snapshot_suffix)
	cloudfront_items_to_invalidate = []
	for item in ('fman.deb', 'fman.dmg', 'fmanSetup.exe'):
		cloudfront_items_to_invalidate.append('/' + item)
		cloudfront_items_to_invalidate.append('/%s/%s' % (version, item))
	create_cloudfront_invalidation(cloudfront_items_to_invalidate)
	record_release_on_server()
	git('checkout', 'master')

def _prompt_for_next_version(release_version):
	next_version = _get_suggested_next_version(release_version)
	return input('Next version (default: %s): ' % next_version) or next_version

def _get_suggested_next_version(version):
	version_parts = version.split('.')
	next_patch = str(int(version_parts[-1]) + 1)
	return '.'.join(version_parts[:-1]) + '.' + next_patch

def _commit_version(settings_path, version, commit_message):
	_replace_in_json(settings_path, 'version', version)
	git('add', settings_path)
	git('commit', '-m', commit_message)

def _replace_in_json(json_path, key, value):
	with open(json_path, 'r') as f:
		old_lines = f.readlines()
	new_lines = []
	found = False
	for line in old_lines:
		new_line = _replace_re_group('\t"%s": "([^"]*)"' % key, line, value)
		if new_line:
			found = True
		else:
			new_line = line
		new_lines.append(new_line)
	if not found:
		raise ValueError('Could not find "%s" mapping in %s' % (key, json_path))
	with open(json_path, 'w') as f:
		f.write(''.join(new_lines))

def _replace_re_group(pattern, string, group_replacement):
	match = re.match(pattern, string)
	if match:
		return string[:match.start(1)] + \
			   group_replacement + \
			   string[match.end(1):]

@command
def arch_docker_image():
	build_dir = path('target/arch-docker-image')
	if exists(build_dir):
		rmtree(build_dir)
	copytree(path('src/build/docker/arch'), build_dir)
	copy(path('conf/ssh/id_rsa'), build_dir)
	copy(path('conf/ssh/id_rsa.pub'), build_dir)
	_build_docker_image('fman/arch', build_dir, path('cache/arch'))
	arch(['/bin/bash', '-c',
		  'python -m venv venv && '
		  'source venv/bin/activate && '
		  'pip install -r requirements/arch.txt'
	])

@command
def ubuntu_docker_image():
	build_dir = path('target/ubuntu-docker-image')
	if exists(build_dir):
		rmtree(build_dir)
	copytree(path('src/build/docker/ubuntu'), build_dir)
	copy(path('conf/ssh/id_rsa'), build_dir)
	copy(path('conf/ssh/id_rsa.pub'), build_dir)
	_build_docker_image('fman/ubuntu', build_dir, path('cache/ubuntu'))
	ubuntu(['/bin/bash', '-c',
		'python3.5 -m venv venv && '
		'source venv/bin/activate && '
		'pip install -r requirements/ubuntu.txt'
	])

@command
def ubuntu(extra_args=None):
	_run_docker_image('fman/ubuntu', path('cache/ubuntu'), extra_args)

@command
def arch(extra_args=None):
	_run_docker_image('fman/arch', path('cache/arch'), extra_args)

def _build_docker_image(image_name, context_dir, cache_dir):
	if isdir(cache_dir):
		subprocess.run(['sudo', 'rm', '-rf', cache_dir])
	subprocess.run(
		['docker', 'build', '--pull', '-t', image_name, context_dir], check=True
	)
	makedirs(cache_dir, exist_ok=True)

def _run_docker_image(image_name, cache_dir, extra_args=None):
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

if __name__ == '__main__':
	project_dir = dirname(__file__)
	fbs.cmdline.main(project_dir)