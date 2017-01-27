from build_impl import run, path, copy_framework, get_canonical_os_name, \
	OPTIONS, copy_python_library, upload_file, run_on_server,\
	check_output_decode, get_path_on_server, run_pyinstaller, \
	copy_with_filtering
from glob import glob
from os import unlink, rename, symlink, makedirs
from os.path import basename, join, exists, splitext
from shutil import rmtree, copy
from tempfile import TemporaryDirectory

def app():
	if not exists(path('target/fman.icns')):
		icon()
	run_pyinstaller(extra_args=[
		'--windowed', '--osx-bundle-identifier', 'io.fman.fman',
		'--icon', path('target/fman.icns')
	])
	_remove_unwanted_pyinstaller_files()
	_fix_sparkle_delta_updates()
	copy_with_filtering(
		path('src/main/resources/base'),
		dest_dir=path('target/fman.app/Contents/Resources')
	)
	copy_with_filtering(
		path('src/main/resources/mac'), dest_dir=path('target/fman.app')
	)
	copy_framework(
		path('lib/mac/Sparkle-1.14.0/Sparkle.framework'),
		path('target/fman.app/Contents/Frameworks/Sparkle.framework')
	)
	copy_python_library(
		'osxtrash', path('target/fman.app/Contents/Resources/Plugins/Core')
	)
	copy_python_library(
		'ordered_set', path('target/fman.app/Contents/Resources/Plugins/Core')
	)

def icon():
	_generate_iconset()
	run(['iconutil', '-c', 'icns', path('target/fman.iconset')])

def _generate_iconset():
	makedirs(path('target/fman.iconset'), exist_ok=True)
	for icon_png in glob(path('src/main/icons/base/*.png')):
		size = int(splitext(basename(icon_png))[0])
		dest_name = 'icon_%dx%d.png' % (size, size)
		copy(icon_png, path('target/fman.iconset/' + dest_name))

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
		path('bin/mac/yoursway-create-dmg/create-dmg'), '--volname', 'fman',
		'--app-drop-link', '0', '10', '--icon', 'fman', '200', '10',
		 path('target/fman.dmg'), path('target/fman.app')
	])

def sign_dmg():
	run([
		'codesign', '--verbose',
		'-s', "Developer ID Application: Michael Herrmann",
		path('target/fman.dmg')
	])

def create_autoupdate_files():
	run([
		'ditto', '-c', '-k', '--sequesterRsrc', '--keepParent',
		path('target/fman.app'),
		path('target/autoupdate/%s.zip' % OPTIONS['version'])
	])
	_create_autoupdate_patches()

def _create_autoupdate_patches():
	version_files = _sync_cache_with_server()
	if not version_files:
		return
	get_version = lambda version_file: splitext(basename(version_file))[0]
	get_version_tpl = lambda vf: _version_str_to_tuple(get_version(vf))
	latest_version = sorted(version_files, key=get_version_tpl)[-1]
	new_version = OPTIONS['version']
	if _version_str_to_tuple(new_version) <= get_version_tpl(latest_version):
		raise ValueError(
			"Version being built (%s) is <= latest version on server (%s)."
			% (new_version, get_version(latest_version))
		)
	for version_file in version_files:
		version = get_version(version_file)
		print('Creating patch %s -> %s.' % (version, new_version))
		with TemporaryDirectory() as tmp_dir:
			# Use ditto instead of Python's ZipFile because the latter does not
			# give 100% the same result, making Sparkle's hash check fail:
			run(['ditto', '-x', '-k', version_file, tmp_dir])
			run([
				path('lib/mac/Sparkle-1.14.0/bin/BinaryDelta'), 'create',
				join(tmp_dir, 'fman.app'), path('target/fman.app'),
				path('target/autoupdate/%s-%s.delta' % (version, new_version))
			])

def _sync_cache_with_server():
	result = []
	if OPTIONS['release']:
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
	updates_dir = get_path_on_server(_get_updates_dir())
	hash_cmd = ' ; '.join([
		# Prevent literal string ".../*.zip" from being passed to for loop below
		# when there is no .zip file:
		'shopt -s nullglob',
		'for f in %s/*.zip'  % updates_dir,
			'do shasum -a 256 $f',
		'done'
	])
	if OPTIONS['release']:
		shasums_lines = run_on_server(hash_cmd)
	else:
		shasums_lines = check_output_decode(hash_cmd, shell=True)
	lines = [line for line in shasums_lines.split('\n')[:-1]]
	result = []
	for line in lines:
		shasum, version_path = line.split(maxsplit=1)
		result.append((version_path, shasum))
	return result

def _shasum(path_):
	return check_output_decode(
		'shasum -a 256 %s | cut -c 1-64' % path_, shell=True
	)[:-1]

def _download_from_server(file_path, dest_dir):
	print('Downloading %s.' % file_path)
	if OPTIONS['release']:
		run(['scp', OPTIONS['server_user'] + ':' + file_path, dest_dir])
	else:
		copy(file_path, dest_dir)

def _version_str_to_tuple(version_str):
	return tuple(map(int, version_str.split('.')))

def _version_tuple_to_str(version_tuple):
	return '.'.join(map(str, version_tuple))

def upload():
	upload_file(path('target/fman.dmg'), 'downloads')
	updates_dir = _get_updates_dir()
	upload_file(
		path('target/autoupdate/%s.zip' % OPTIONS['version']), updates_dir
	)
	for patch_file in glob(path('target/autoupdate/*.delta')):
		upload_file(patch_file, updates_dir)

def _get_updates_dir():
	return 'updates/' + get_canonical_os_name()