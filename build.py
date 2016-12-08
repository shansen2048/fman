from build_impl import path, is_windows, is_mac, is_linux, OPTIONS
from os import unlink, listdir, remove
from os.path import join, isdir, isfile, islink, expanduser
from shutil import rmtree
from unittest import TestSuite, TextTestRunner, defaultTestLoader

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
	OPTIONS['release'] = True
	publish()

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