from build_impl import path, run, copy_with_filtering, unzip, copy_framework, \
	get_canonical_os_name, is_windows, is_osx, is_linux
from glob import glob
from os import rename, symlink, unlink, makedirs, listdir, remove
from os.path import exists, join, basename, splitext, isdir, isfile, islink
from shutil import rmtree, copy
from subprocess import check_output
from tempfile import TemporaryDirectory

import json
import sys

VERSION = '0.0.3'

LOCAL_STATICFILES_DIR = '/Users/michael/dev/fman.io/static'
SERVER_STATICFILES_DIR = '/home/fman/src/static'
SERVER_USER = 'fman@fman.io'

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
		extra_env={'PYTHONPATH': path('src/main/python')}
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
	pythonpath = ':'.join(map(path, [
		'src/main/python', 'src/unittest/python', 'src/integrationtest/python'
	]))
	run(
		['python', '-m', 'unittest', 'fman_unittest', 'fman_integrationtest'],
		extra_env={'PYTHONPATH': pythonpath}
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
	version_files = _sync_cache_with_server()
	if not version_files:
		return
	get_version = lambda version_file: splitext(basename(version_file))[0]
	get_version_tpl = lambda vf: _version_str_to_tuple(get_version(vf))
	latest_version = sorted(version_files, key=get_version_tpl)[-1]
	if _version_str_to_tuple(VERSION) <= get_version_tpl(latest_version):
		raise ValueError(
			"Version being built (%s) is <= latest version on server (%s)."
			% (VERSION, get_version(latest_version))
		)
	for version_file in version_files:
		version = get_version(version_file)
		print('Creating patch %s -> %s.' % (version, VERSION))
		with TemporaryDirectory() as tmp_dir:
			# Use ditto instead of Python's ZipFile because the latter does not
			# give 100% the same result, making Sparkle's hash check fail:
			run(['ditto', '-x', '-k', version_file, tmp_dir])
			run([
				path('lib/osx/Sparkle-1.14.0/bin/BinaryDelta'), 'create',
				join(tmp_dir, 'fman.app'), path('target/fman.app'),
				path('target/autoupdate/%s-%s.delta' % (version, VERSION))
			])

def _sync_cache_with_server():
	result = []
	if RELEASE:
		cache_dir = path('target/cache/server')
	else:
		cache_dir = path('target/cache/local')
	makedirs(cache_dir, exist_ok=True)
	versions_on_server = _get_versions_on_server()
	for version_file, shasum in versions_on_server:
		cached_version = join(cache_dir, basename(version_file))
		if not exists(cached_version):
			_download_from_server(version_file, cache_dir)
		else:
			if _shasum(cached_version) != shasum:
				print(
					'Warning: shasum of %s differs on server.' % cached_version
				)
				_download_from_server(version_file, cache_dir)
		result.append(cached_version)
	return result

def _get_versions_on_server():
	if RELEASE:
		updates_dir = _get_updates_dir(SERVER_STATICFILES_DIR)
	else:
		updates_dir = _get_updates_dir(LOCAL_STATICFILES_DIR)
	hash_cmd = ' ; '.join([
		# Prevent literal string ".../*.zip" from being passed to for loop below
		# when there is no .zip file:
		'shopt -s nullglob',
		'for f in %s/*.zip'  % updates_dir,
			'do shasum -a 256 $f',
		'done'
	])
	if RELEASE:
		shasums_lines = _run_on_server(SERVER_USER, hash_cmd)
	else:
		shasums_lines = _check_output_decode(hash_cmd, shell=True)
	lines = [line for line in shasums_lines.split('\n')[:-1]]
	result = []
	for line in lines:
		shasum, version_path = line.split(maxsplit=1)
		result.append((version_path, shasum))
	return result

def _shasum(path_):
	return _check_output_decode(
		'shasum -a 256 %s | cut -c 1-64' % path_, shell=True
	)[:-1]

def _download_from_server(file_path, dest_dir):
	print('Downloading %s.' % file_path)
	if RELEASE:
		run(['scp', SERVER_USER + ':' + file_path, dest_dir])
	else:
		copy(file_path, dest_dir)

def _run_on_server(user_server, command):
	return _check_output_decode(['ssh', user_server, command])

def _check_output_decode(*args, **kwargs):
	return check_output(*args, **kwargs).decode(sys.stdout.encoding)

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
	RELEASE = args.release
	result = globals()[args.cmd](*args.args)
	if result:
		print(result)