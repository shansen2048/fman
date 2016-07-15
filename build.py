from build_impl import path, run, copy_with_filtering, unzip, copy_framework, \
	get_canonical_os_name, is_windows, is_osx, is_linux
from glob import glob
from os import rename, symlink, listdir, unlink
from os.path import exists, join, basename, splitext
from shutil import rmtree, copy
from subprocess import check_output
from tempfile import TemporaryDirectory

import json
import sys

VERSION = '0.0.1'

RELEASE = False

LOCAL_STATICFILES_DIR = '/Users/michael/dev/fman.io/static'
SERVER_STATICFILES_DIR = '/home/fman/src/static'
SERVER_USER = 'fman@fman.io'

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
		'--distpath', path('target'),
		'--specpath', path('target/build'),
		'--workpath', path('target/build'),
		path('src/main/python/fman/main.py')
	])
	_remove_unwanted_pyinstaller_files()
	_fix_sparkle_delta_updates()
	generate_resources(dest_dir=path('target/fman.app/Contents/Resources'))
	copy_with_filtering(
		path('src/main/resources/osx/Info.plist'),
		path('target/fman.app/Contents'),
		_get_filter()
	)
	copy_framework(
		path('lib/osx/Sparkle-1.14.0/Sparkle.framework'),
		path('target/fman.app/Contents/Frameworks/Sparkle.framework')
	)

def _remove_unwanted_pyinstaller_files():
	for unwanted in ('include', 'lib', 'lib2to3'):
		unlink(path('target/fman.app/Contents/MacOS/' + unwanted))
		rmtree(path('target/fman.app/Contents/Resources/' + unwanted))

def _fix_sparkle_delta_updates():
	# Sparkle's Delta Updates mechanism does not support signed non-Mach-O files
	# in Contents/MacOS. base_library.zip, which is created by PyInstaller,
	# violates this. We therefore move base_library.zip to Contents/Resources.
	# Fortunately, everything still works if we then create a symlink
	# MacOS/base_library.zip -> ../Resources/base_library.zip.
	rename(
		path('target/fman.app/Contents/MacOS/base_library.zip'),
		path('target/fman.app/Contents/Resources/base_library.zip')
	)
	symlink(
		'../Resources/base_library.zip',
		path('target/fman.app/Contents/MacOS/base_library.zip')
	)

def sign_app():
	run([
		'codesign', '--deep', '--verbose',
		'-s', "Developer ID Application: Michael Herrmann",
		path('target/fman.app')
	])

def dmg():
	run([
		path('bin/osx/yoursway-create-dmg/create-dmg'), '--volname', 'fman',
		'--app-drop-link', '0', '10', '--icon', 'fman', '200', '10',
		 path('target/fman.dmg'), path('target/fman.app')
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
		create_autoupdate_files()
		upload()
	elif is_linux():
		esky()
	else:
		raise ValueError('Unknown operating system.')

def create_autoupdate_files():
	run([
		'ditto', '-c', '-k', '--sequesterRsrc', '--keepParent',
		path('target/fman.app'), path('target/autoupdate/%s.zip' % VERSION)
	])
	_create_autoupdate_patches()

def _create_autoupdate_patches():
	latest_version = _get_latest_version_on_server()
	if latest_version:
		old_version_tpl, old_version_zip = latest_version
		old_version = _version_tuple_to_str(old_version_tpl)
		new_version = VERSION
		new_version_tpl = _version_str_to_tuple(new_version)
		if new_version_tpl <= old_version_tpl:
			raise ValueError(
				"Version being built (%s) is <= latest version on server (%s)."
				% (new_version, old_version)
			)
		print('Creating patch %s -> %s.' % (old_version, new_version))
		with TemporaryDirectory() as tmp_dir:
			if RELEASE:
				run(['scp', SERVER_USER + ':' + old_version_zip, tmp_dir])
				old_version_zip = join(tmp_dir, basename(old_version_zip))
			# Use ditto instead of Python's ZipFile because the latter does not
			# give 100% the same result, making Sparkle's hash check fail:
			run(['ditto', '-x', '-k', old_version_zip, tmp_dir])
			run([
				path('lib/osx/Sparkle-1.14.0/bin/BinaryDelta'), 'create',
				join(tmp_dir, 'fman.app'), path('target/fman.app'),
				path(
					'target/autoupdate/%s-%s.delta' % (old_version, new_version)
				)
			])

def _get_latest_version_on_server():
	if RELEASE:
		updates_dir = _get_updates_dir(SERVER_STATICFILES_DIR)
		files = _listdir_remote(SERVER_USER, updates_dir)
	else:
		updates_dir = _get_updates_dir(LOCAL_STATICFILES_DIR)
		files = _listdir_absolute(updates_dir)
	versions = []
	for f in files:
		version_str, ext = splitext(basename(f))
		if ext != '.zip':
			continue
		try:
			version_tpl = _version_str_to_tuple(version_str)
		except ValueError:
			continue
		versions.append((version_tpl, f))
	if versions:
		return sorted(versions)[-1]

def _listdir_remote(user_server, dir_):
	files_lines = check_output([
		'ssh', user_server, 'for n in %s/*; do echo $n; done' % dir_
	]).decode(sys.stdout.encoding)
	return [line.rstrip() for line in files_lines.split('\n')][:-1]

def _listdir_absolute(dir_):
	return [join(dir_, f) for f in listdir(dir_)]

def _version_str_to_tuple(version_str):
	return tuple(map(int, version_str.split('.')))

def _version_tuple_to_str(version_tuple):
	return '.'.join(map(str, version_tuple))

def upload():
	if RELEASE:
		staticfiles_dir = SERVER_STATICFILES_DIR
	else:
		staticfiles_dir = LOCAL_STATICFILES_DIR
	_upload_file(path('target/fman.dmg'), _get_downloads_dir(staticfiles_dir))
	updates_dir = _get_updates_dir(staticfiles_dir)
	_upload_file(path('target/autoupdate/%s.zip' % VERSION), updates_dir)
	for patch_file in glob(path('target/autoupdate/*.delta')):
		_upload_file(patch_file, updates_dir)
	if RELEASE:
		# The server serves its static files from static-collected/. The
		# "Appcast.xml" view looks inside static/. So we need the files in both
		# locations. Run `collectstatic` to have Django copy them from static/
		# to static-collected/.
		run([
			'ssh', SERVER_USER,
			'cd src/ ; '
			'source venv/bin/activate ; '
			'python manage.py collectstatic --noinput'
		])

def _upload_file(f, dest_dir):
	print('Uploading %s...' % basename(f))
	if RELEASE:
		run(['scp', f, SERVER_USER + ':' + dest_dir])
	else:
		copy(f, dest_dir)

def _get_updates_dir(staticfiles_dir):
	return staticfiles_dir + '/updates/' + get_canonical_os_name()

def _get_downloads_dir(staticfiles_dir):
	return staticfiles_dir + '/downloads/'

def release():
	global RELEASE
	RELEASE = True
	publish()

def clean():
	rmtree(path('target'), ignore_errors=True)

if __name__ == '__main__':
	result = globals()[sys.argv[1]](*sys.argv[2:])
	if result:
		print(result)