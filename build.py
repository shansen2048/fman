from build_impl import path, is_windows, is_mac, is_linux, OPTIONS, git, \
	create_cloudfront_invalidation
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
	'gpg_key': 'B015FE599CFAF7EB',
	'aws_access_key_id': 'AKIAIWTB3R6KKMMTWXEA',
	'aws_secret_access_key': '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',
	'aws_bucket': 'fman',
	'aws_distribution_id': 'E36JGR8Q7NMYHR'
})

if is_windows():
	from build_impl.windows import exe, installer, sign_exe, sign_installer, \
		add_installer_manifest, upload
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
		upload()
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