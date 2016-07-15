from build_impl import path, run, copy_with_filtering, unzip, copy_framework, \
	get_canonical_os_name, is_windows, is_osx, is_linux
from glob import glob
from os.path import exists
from shutil import rmtree, copy

import json
import sys

VERSION = '0.0.1'

RELEASE = False

LOCAL_STATICFILES_DIR = '/Users/michael/dev/fman.io/static'
SERVER_STATICFILES_DIR = 'fman@fman.io:/home/fman/src/static'

MAIN_PYTHON_PATH = path('src/main/python')
TEST_PYTHON_PATH = ':'.join(map(path,
	['src/main/python', 'src/unittest/python', 'src/integrationtest/python']
))

FILES_TO_FILTER = [path('src/main/resources/base/default_settings.json')]
EXCLUDE_RESOURCES = [path('src/main/resources/osx/Info.plist')]

def generate_resources(dest_dir=path('target/resources')):
	def copy_resources(src_dir):
		copy_with_filtering(
			src_dir, dest_dir, _get_filter(), FILES_TO_FILTER, EXCLUDE_RESOURCES
		)
	copy_resources(path('src/main/resources/base'))
	os_resources_dir = path('src/main/resources/' + get_canonical_os_name())
	if exists(os_resources_dir):
		copy_resources(os_resources_dir)

def _get_filter():
	filter_type = 'release' if RELEASE else 'local'
	filter_path = path('src/main/filters/filter-%s.json' % filter_type)
	with open(filter_path, 'r') as f:
		result = json.load(f)
	result['version'] = VERSION
	return result

def esky():
	generate_resources()
	run(
		['python', path('setup.py'), 'bdist_esky'],
		extra_env={'PYTHONPATH': MAIN_PYTHON_PATH}
	)

def app():
	run([
		'pyinstaller',
		'--name', 'fman',
		'--osx-bundle-identifier', 'io.fman.fman',
		'--windowed',
		'--distpath', path('target/dist'),
		'--workpath', path('target/build'),
		'--specpath', path('target'),
		path('src/main/python/fman/main.py')
	])
	generate_resources(dest_dir=path('target/dist/fman.app/Contents/Resources'))
	info_plist = path('src/main/resources/osx/Info.plist')
	copy_with_filtering(
		info_plist, path('target/dist/fman.app/Contents'), _get_filter()
	)
	copy_framework(
		path('lib/osx/Sparkle-1.14.0/Sparkle.framework'),
		path('target/dist/fman.app/Contents/Frameworks/Sparkle.framework')
	)

def sign_app():
	run([
		'codesign', '--deep', '--verbose',
		'-s', "Developer ID Application: Michael Herrmann",
		path('target/dist/fman.app')
	])

def dmg():
	run([
		path('bin/osx/yoursway-create-dmg/create-dmg'), '--volname', 'fman',
		'--app-drop-link', '0', '10', '--icon', 'fman', '200', '10',
		 path('target/fman.dmg'), path('target/dist/fman.app')
	])

def sign_dmg():
	run([
		'codesign', '--verbose',
		'-s', "Developer ID Application: Michael Herrmann",
		path('target/fman.dmg')
	])

def setup():
	esky()
	latest_zip = sorted(glob(path('target/fman-*.zip')))[-1]
	unzip(latest_zip, path('target/exploded'))
	run(['makensis', path('src/main/Setup.nsi')])

def test():
	run(
		['python', '-m', 'unittest', 'fman_unittest', 'fman_integrationtest'],
		extra_env={'PYTHONPATH': TEST_PYTHON_PATH}
	)

def publish():
	if is_windows():
		setup()
	elif is_osx():
		app()
		sign_app()
		dmg()
		sign_dmg()
		pack_update()
		upload()
	elif is_linux():
		esky()
	else:
		raise ValueError('Unknown operating system.')

def pack_update():
	run([
		'ditto', '-c', '-k', '--sequesterRsrc', '--keepParent',
		path('target/dist/fman.app'), path('target/fman-%s.zip' % VERSION)
	])

def upload():
	updates_dir = '/updates/' + get_canonical_os_name()
	downloads_dir = '/downloads/'
	if RELEASE:
		run([
			'scp', path('target/fman.dmg'),
			SERVER_STATICFILES_DIR + downloads_dir
		])
		run([
			'scp', path('target/fman-%s.zip' % VERSION),
			SERVER_STATICFILES_DIR + updates_dir
		])
	else:
		copy(path('target/fman.dmg'), LOCAL_STATICFILES_DIR + downloads_dir)
		copy(
			path('target/fman-%s.zip' % VERSION),
			LOCAL_STATICFILES_DIR + updates_dir
		)

def clean():
	rmtree(path('target'), ignore_errors=True)

if __name__ == '__main__':
	globals()[sys.argv[1]](*sys.argv[2:])