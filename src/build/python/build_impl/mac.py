from build_impl import copy_framework, get_canonical_os_name, SETTINGS, \
	copy_python_library, upload_file, run_on_server, check_output_decode, \
	get_path_on_server, upload_installer_to_aws
from fbs import command
from fbs.conf import path
from fbs.freeze.mac import freeze_mac
from glob import glob
from os import makedirs
from os.path import basename, join, exists, splitext
from shutil import copy, rmtree
from subprocess import run
from tempfile import TemporaryDirectory

@command
def app():
	freeze_mac()
	rmtree(path('${freeze_dir}/Contents/Resources/Plugins/Core/bin/linux'))
	rmtree(path('${freeze_dir}/Contents/Resources/Plugins/Core/bin/windows'))
	copy_framework(
		path('lib/mac/Sparkle-1.14.0/Sparkle.framework'),
		path('${freeze_dir}/Contents/Frameworks/Sparkle.framework')
	)
	copy_python_library(
		'osxtrash', path('${freeze_dir}/Contents/Resources/Plugins/Core')
	)
	copy_python_library(
		'ordered_set', path('${freeze_dir}/Contents/Resources/Plugins/Core')
	)

@command
def sign_app():
	run([
		'codesign', '--deep', '--verbose',
		'-s', "Developer ID Application: Michael Herrmann",
		path('${freeze_dir}')
	], check=True)

@command
def dmg():
	run([
		path('bin/mac/yoursway-create-dmg/create-dmg'), '--volname', 'fman',
		'--app-drop-link', '0', '10', '--icon', 'fman', '200', '10',
		 path('target/fman.dmg'), path('${freeze_dir}')
	], check=True)

@command
def sign_dmg():
	run([
		'codesign', '--verbose',
		'-s', "Developer ID Application: Michael Herrmann",
		path('target/fman.dmg')
	], check=True)

def create_autoupdate_files():
	run([
		'ditto', '-c', '-k', '--sequesterRsrc', '--keepParent',
		path('${freeze_dir}'),
		path('target/autoupdate/%s.zip' % SETTINGS['version'])
	], check=True)
	_create_autoupdate_patches()

def _create_autoupdate_patches(num=10):
	get_version = lambda version_file: splitext(basename(version_file))[0]
	get_version_tpl = lambda vf: _version_str_to_tuple(get_version(vf))
	version_files = sorted(_sync_cache_with_server(), key=get_version_tpl)
	if not version_files:
		return
	latest_version = version_files[-1]
	new_version = SETTINGS['version']
	if _version_str_to_tuple(new_version) <= get_version_tpl(latest_version):
		raise ValueError(
			"Version being built (%s) is <= latest version on server (%s)."
			% (new_version, get_version(latest_version))
		)
	for version_file in version_files[-num:]:
		version = get_version(version_file)
		print('Creating patch %s -> %s.' % (version, new_version))
		with TemporaryDirectory() as tmp_dir:
			# Use ditto instead of Python's ZipFile because the latter does not
			# give 100% the same result, making Sparkle's hash check fail:
			run(['ditto', '-x', '-k', version_file, tmp_dir], check=True)
			freeze_dir = path('${freeze_dir}')
			run([
				path('lib/mac/Sparkle-1.14.0/bin/BinaryDelta'), 'create',
				join(tmp_dir, basename(freeze_dir)), freeze_dir,
				path('target/autoupdate/%s-%s.delta' % (version, new_version))
			], check=True)

def _sync_cache_with_server():
	result = []
	if SETTINGS['release']:
		cache_dir = path('cache/server')
	else:
		cache_dir = path('cache/local')
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
	if SETTINGS['release']:
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
	if SETTINGS['release']:
		# If the file permissions are too open, macOS reports an error and
		# aborts:
		run(['chmod', '600', SETTINGS['ssh_key']], check=True)
		run([
			'scp', '-i', SETTINGS['ssh_key'],
			SETTINGS['server_user'] + ':' + file_path, dest_dir
		], check=True)
	else:
		copy(file_path, dest_dir)

def _version_str_to_tuple(version_str):
	return tuple(map(int, version_str.split('.')))

def _version_tuple_to_str(version_tuple):
	return '.'.join(map(str, version_tuple))

@command
def upload():
	updates_dir = _get_updates_dir()
	upload_file(
		path('target/autoupdate/%s.zip' % SETTINGS['version']), updates_dir
	)
	for patch_file in glob(path('target/autoupdate/*.delta')):
		upload_file(patch_file, updates_dir)
	if SETTINGS['release']:
		upload_installer_to_aws('fman.dmg')

def _get_updates_dir():
	return 'updates/' + get_canonical_os_name()