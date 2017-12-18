from fbs import OPTIONS
from os.path import dirname
OPTIONS['project_dir'] = dirname(__file__)

from build_impl import path, OPTIONS, git, create_cloudfront_invalidation, \
	read_filter
from fbs import run
from fbs.platform import is_windows, is_mac, is_linux, is_ubuntu, is_arch_linux
from os import unlink, listdir, remove, makedirs
from os.path import join, isdir, isfile, islink, expanduser
from shutil import rmtree, copytree, copy
from subprocess import DEVNULL
from unittest import TestSuite, TextTestRunner, defaultTestLoader

import re
import subprocess
import sys

OPTIONS.update({
	'venv_dir': path('venv'),
	'main_module': path('src/main/python/fman/main.py'),
	'local_media_dir': expanduser('~/dev/fman.io/media'),
	'server_media_dir': '/home/fman/src/media',
	'server_user': 'fman@fman.io',
	'ssh_key': path('conf/ssh/id_rsa'),
	'files_to_filter': [
		path('src/main/resources/base/constants.json'),
		path('src/main/resources/mac/Contents/Info.plist'),
		path('src/main/resources/mac/Contents/SharedSupport/bin/fman')
	],
	'gpg_key': 'B015FE599CFAF7EB',
	'gpg_pass': 'fenst4r',
	'aws_access_key_id': 'AKIAIWTB3R6KKMMTWXEA',
	'aws_secret_access_key': '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',
	'aws_bucket': 'fman',
	'aws_distribution_id': 'E36JGR8Q7NMYHR'
})

if is_windows():
	from build_impl.windows import init, exe, installer, sign_exe, \
		sign_installer, add_installer_manifest, upload
elif is_mac():
	from build_impl.mac import init, app, sign_app, dmg, sign_dmg, upload, \
		create_autoupdate_files
elif is_linux():
	if is_ubuntu():
		from build_impl.ubuntu import init, exe, deb, upload
	elif is_arch_linux():
		from build_impl.arch import init, exe, pkg, sign_pkg, repo, pkgbuild, \
			upload
	else:
		raise NotImplementedError()

def test():
	test_dirs = list(map(path, [
		'src/unittest/python', 'src/integrationtest/python',
		'src/main/resources/base/Plugins/Core'
	]))
	sys.path.append(path('src/main/python'))
	suite = TestSuite()
	for test_dir in test_dirs:
		sys.path.append(test_dir)
		for dir_name in listdir(test_dir):
			dir_path = join(test_dir, dir_name)
			if isfile(join(dir_path, '__init__.py')):
				suite.addTest(defaultTestLoader.discover(
					dir_name, top_level_dir=test_dir
				))
	TextTestRunner().run(suite)

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
		dmg()
		sign_dmg()
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

def release():
	clean()
	OPTIONS['release'] = True
	OPTIONS.update(read_filter())
	version = OPTIONS['version']
	if version.endswith(snapshot_suffix):
		release_version = version[:-len(snapshot_suffix)]
		print('Releasing version %s' % release_version)
		next_version = _get_suggested_next_version(release_version)
		next_version = input('Next version (default: %s): ' % next_version) \
					   or next_version
		_commit_version(
			release_version, 'Set version number for release ' + release_version
		)
		OPTIONS['version'] = release_version
		publish()
		release_tag = 'v' + release_version
		git('tag', release_tag)
		_commit_version(
			next_version + snapshot_suffix,
			'Bump version for next development iteration'
		)
		git('push', '-u', 'origin', 'master')
		git('push', 'origin', release_tag)
		git('checkout', release_tag)
		print(
			'\nDone. Run\n\n'
			'    git pull\n'
			'    git checkout %s\n'
			'    python build.py release\n'
			'    git checkout master\n\n'
			'on the other OSs now, then come back here and do:\n\n'
			'    python build.py post_release\n'
			% release_tag
		)
	else:
		publish()

snapshot_suffix = '-SNAPSHOT'

def post_release():
	version = OPTIONS['version']
	assert not version.endswith(snapshot_suffix)
	cloudfront_items_to_invalidate = []
	for item in ('fman.deb', 'fman.dmg', 'fmanSetup.exe'):
		cloudfront_items_to_invalidate.append('/' + item)
		cloudfront_items_to_invalidate.append('/%s/%s' % (version, item))
	create_cloudfront_invalidation(cloudfront_items_to_invalidate)
	git('checkout', 'master')

def _get_suggested_next_version(version):
	version_parts = version.split('.')
	next_patch = str(int(version_parts[-1]) + 1)
	return '.'.join(version_parts[:-1]) + '.' + next_patch

def _commit_version(version, commit_message):
	filter_path = path('src/main/filters/filter-local.json')
	_replace_in_json(filter_path, 'version', version)
	git('add', filter_path)
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

def clean():
	try:
		rmtree(path('target'))
	except FileNotFoundError:
		return
	except OSError:
		# In a docker container, target/ may be mounted so we can't delete it.
		# Delete its contents instead:
		for f in listdir(path('target')):
			if f != 'cache':
				fpath = join(path('target'), f)
				if isdir(fpath):
					rmtree(fpath, ignore_errors=True)
				elif isfile(fpath):
					remove(fpath)
				elif islink(fpath):
					unlink(fpath)

def arch_docker_image():
	build_dir = path('target/arch-docker-image')
	copytree(path('src/main/docker/arch'), build_dir)
	copy(path('conf/ssh/id_rsa'), build_dir)
	copy(path('conf/ssh/id_rsa.pub'), build_dir)
	_build_docker_image('fman/arch', build_dir, path('cache/arch'))
	arch(['/bin/bash', '-c', 'python build.py init'])

def ubuntu_docker_image():
	build_dir = path('target/ubuntu-docker-image')
	copytree(path('src/main/docker/ubuntu'), build_dir)
	copy(path('conf/ssh/id_rsa'), build_dir)
	copy(path('conf/ssh/id_rsa.pub'), build_dir)
	_build_docker_image('fman/ubuntu', build_dir, path('cache/ubuntu'))
	ubuntu(['/bin/bash', '-c', 'python3.5 build.py init'])

def ubuntu(extra_args=None):
	_run_docker_image('fman/ubuntu', path('cache/ubuntu'), extra_args)

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

from argparse import ArgumentParser
if __name__ == '__main__':
	parser = ArgumentParser(description='Build fman.')
	parser.add_argument('cmd')
	parser.add_argument('args', metavar='arg', nargs='*')
	parser.add_argument(
		'--release', dest='release', action='store_const', const=True,
		default=False
	)
	args = parser.parse_args()
	OPTIONS['release'] = args.release
	OPTIONS.update(read_filter())
	result = globals()[args.cmd](*args.args)
	if result:
		print(result)