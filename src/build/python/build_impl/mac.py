from build_impl import copy_framework, SETTINGS, copy_python_library, \
	upload_file, run_on_server, check_output_decode, get_path_on_server, \
	upload_installer_to_aws
from fbs import path
from fbs.cmdline import command
from fbs.freeze.mac import freeze_mac
from glob import glob
from os import makedirs, remove
from os.path import basename, join, exists, splitext
from shutil import copy, rmtree, make_archive
from subprocess import run, PIPE, CalledProcessError, SubprocessError
from tempfile import TemporaryDirectory
from time import sleep

import plistlib

_UPDATES_DIR = 'updates/mac'

@command
def freeze():
	freeze_mac()
	rmtree(path('${core_plugin_in_freeze_dir}/bin/linux'))
	rmtree(path('${core_plugin_in_freeze_dir}/bin/windows'))
	# Open Sans is only used on Linux. Further, it fails to load on some users'
	# Windows systems (see fman issue #480). Remove it to avoid problems,
	# improve startup performance and decrease fman's download size.
	# (Also note that a more elegant solution would be to only place
	# Open Sans.ttf in src/main/resources/*linux*/Plugins/Core. But the current
	# implementation cannot handle multiple dirs .../resources/main,
	# .../resources/linux for one plugin.)
	remove(path('${core_plugin_in_freeze_dir}/Open Sans.ttf'))
	# Similarly for Roboto Bold.ttf. It is only used on Windows:
	remove(path('${core_plugin_in_freeze_dir}/Roboto Bold.ttf'))
	copy_framework(
		path('lib/mac/Sparkle-1.18.1/Sparkle.framework'),
		path('${freeze_dir}/Contents/Frameworks/Sparkle.framework')
	)
	copy_python_library('osxtrash', path('${core_plugin_in_freeze_dir}'))

@command
def sign():
	app_dir = path('${freeze_dir}')
	run([
		'codesign', '--deep', '--verbose', '--options', 'runtime',
		'-s', "Developer ID Application: Michael Herrmann",
		app_dir
	], check=True)
	zip_path = make_archive(
		app_dir, 'zip', path('target'), basename(path('${freeze_dir}'))
	)
	_notarize(zip_path)
	_staple(app_dir)

def _staple(file_path):
	run(['xcrun', 'stapler', 'staple', file_path], check=True)

def _notarize(file_path, query_interval_secs=10):
	request_uuid = _query_altool([
		'--notarize-app', '-t', 'osx', '-f', file_path,
		'--primary-bundle-id', SETTINGS['mac_bundle_identifier']
	], 'notarization-upload', 'RequestUUID')
	while True:
		status = _query_altool(
			['--notarization-info', request_uuid],
			'notarization-info', 'Status'
		)
		if status != 'in progress':
			break
		print('Waiting for notarization to complete...')
		sleep(query_interval_secs)
	if status != 'success':
		raise RuntimeError('Unexpected notarization status: %r' % status)

def _query_altool(args, k1, k2):
	plist_response = _run_altool(args)
	try:
		return plist_response[k1][k2]
	except KeyError:
		raise KeyError('Unexpected plist response: ' + repr(plist_response))

def _run_altool(args):
	all_args = [
		'xcrun', 'altool', '--output-format', 'xml',
		'-u', SETTINGS['apple_developer_user'],
		'-p', SETTINGS['apple_developer_app_pw']
	] + args
	try:
		process = run(all_args, stdout=PIPE, stderr=PIPE, check=True)
	except CalledProcessError as e:
		raise SubprocessError(
			str(e) + '\nStdout: %s\nStderr: %s' % (e.stdout, e.stderr)
		)
	try:
		return plistlib.loads(process.stdout)
	except plistlib.InvalidFileException:
		raise plistlib.InvalidFileException('Invalid file: %r' % process.stdout)

@command
def sign_installer():
	installer_path = path('target/fman.dmg')
	run([
		'codesign', '--verbose',
		'-s', "Developer ID Application: Michael Herrmann",
		installer_path
	], check=True)
	_notarize(installer_path)
	_staple(installer_path)

@command
def upload():
	_create_autoupdate_files()
	upload_file(
		path('target/autoupdate/%s.zip' % SETTINGS['version']), _UPDATES_DIR
	)
	for patch_file in glob(path('target/autoupdate/*.delta')):
		upload_file(patch_file, _UPDATES_DIR)
	if SETTINGS['release']:
		upload_installer_to_aws('fman.dmg')

def _create_autoupdate_files():
	run([
		'ditto', '-c', '-k', '--sequesterRsrc', '--keepParent',
		path('${freeze_dir}'),
		path('target/autoupdate/%s.zip' % SETTINGS['version'])
	], check=True)
	_create_autoupdate_patches()

def _create_autoupdate_patches(num=5):
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
				path('lib/mac/Sparkle-1.18.1/bin/BinaryDelta'), 'create',
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
	updates_dir = get_path_on_server(_UPDATES_DIR)
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