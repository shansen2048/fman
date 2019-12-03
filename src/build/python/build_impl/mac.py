from build_impl import copy_framework, SETTINGS, copy_python_library, \
	upload_file, upload_installer_to_aws
from fbs import path
from fbs.cmdline import command
from fbs.freeze.mac import freeze_mac
from glob import glob
from os import remove
from os.path import basename
from shutil import rmtree, make_archive
from subprocess import run, PIPE, CalledProcessError, SubprocessError
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
		sleep(query_interval_secs)
		status = _query_altool(
			['--notarization-info', request_uuid],
			'notarization-info', 'Status'
		)
		if status != 'in progress':
			break
		print('Waiting for notarization to complete...')
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