from build_impl import path, is_windows, is_mac, is_linux, OPTIONS, run
from os import unlink, listdir, remove
from os.path import join, isdir, isfile, islink, expanduser
from shutil import rmtree
from unittest import TestSuite, TextTestRunner, defaultTestLoader

import re
import sys

OPTIONS.update({
	'local_staticfiles_dir': expanduser('~/dev/fman.io/static'),
	'server_staticfiles_dir': '/home/fman/src/static',
	'server_user': 'fman@fman.io',
	'files_to_filter': [
		path('src/main/resources/base/constants.json'),
		path('src/main/resources/mac/Contents/Info.plist'),
		path('src/main/resources/mac/Contents/SharedSupport/bin/fman')
	],
	'gpg_key': 'B015FE599CFAF7EB'
})

if is_windows():
	from build_impl.windows import exe, installer, sign_exe, sign_installer, \
		add_installer_manifest
elif is_mac():
	from build_impl.mac import app, sign_app, dmg, sign_dmg, upload, \
		create_autoupdate_files
elif is_linux():
	from build_impl.linux import exe, deb, upload

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
	elif is_mac():
		app()
		sign_app()
		dmg()
		sign_dmg()
		create_autoupdate_files()
		upload()
	elif is_linux():
		exe()
		deb()
		upload()
	else:
		raise ValueError('Unknown operating system.')

def release():
	clean()
	OPTIONS['release'] = True
	version = OPTIONS['version']
	snapshot_suffix = '-SNAPSHOT'
	if version.endswith(snapshot_suffix):
		release_version = version[:-len(snapshot_suffix)]
		print('Releasing version %s' % release_version)
		release_version_parts = release_version.split('.')
		new_patch_v = str(int(release_version_parts[-1]) + 1)
		new_version = '.'.join(release_version_parts[:-1]) + '.' + new_patch_v
		new_version = input('New version (default: %s): ' % new_version) \
					  or new_version
		filter_path = path('src/main/filters/filter-local.json')
		_replace_in_json(filter_path, 'version', release_version)
		run(['git', 'add', filter_path])
		run([
			'git', 'commit', '-m',
			'Set version number for release ' + release_version
		])
		publish()
		release_tag = 'v' + release_version
		run(['git', 'tag', release_tag])
		_replace_in_json(filter_path, 'version', new_version + snapshot_suffix)
		run(['git', 'add', filter_path])
		run([
			'git', 'commit', '-m', 'Bump version for next development iteration'
		])
		run(['git', 'push', '-u', 'origin', 'master'])
		run(['git', 'push', 'origin', release_tag])
	else:
		publish()

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
		target_files = listdir(path('target'))
	except FileNotFoundError:
		return
	for f in target_files:
		if f != 'cache':
			fpath = join(path('target'), f)
			if isdir(fpath):
				rmtree(fpath, ignore_errors=True)
			elif isfile(fpath):
				remove(fpath)
			elif islink(fpath):
				unlink(fpath)

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
	result = globals()[args.cmd](*args.args)
	if result:
		print(result)