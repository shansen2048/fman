from build_impl import upload_installer_to_aws
from build_impl.aws import list_files_on_s3, download_file_from_s3, \
	upload_directory_contents, create_cloudfront_invalidation
from build_impl.linux import postprocess_exe
from fbs import path, SETTINGS
from fbs.cmdline import command
from fbs.freeze.fedora import freeze_fedora
from fnmatch import fnmatch
from os import makedirs
from os.path import exists, join, dirname
from shutil import rmtree, copytree, copy
from subprocess import run, PIPE

import re

@command
def freeze():
	freeze_fedora()
	postprocess_exe()

@command
def sign_installer():
	# Prevent GPG from prompting us for the passphrase when signing:
	_preload_gpg_passphrase()
	run(['rpm', '--addsign', path('target/fman.rpm')])

def _preload_gpg_passphrase():
	keygrip = _get_keygrip(SETTINGS['gpg_key'])
	_run(
		'/usr/libexec/gpg-preset-passphrase', '--passphrase',
		 SETTINGS['gpg_pass'], '--preset', keygrip
	)

def _get_keygrip(pubkey_id):
	output = _run('gpg2', '--with-keygrip', '-K', pubkey_id)
	lines = output.split('\n')
	for i, line in enumerate(lines):
		if line.endswith('[S]'):
			keygrip_line = lines[i + 1]
			m = re.match(r' +Keygrip = ([A-Z0-9]{40})', keygrip_line)
			if not m:
				raise RuntimeError('Unexpected output: ' + keygrip_line)
			return m.group(1)
	raise RuntimeError('Keygrip not found. Output was:\n' + output)

@command
def upload():
	if SETTINGS['release']:
		upload_installer_to_aws('fman.rpm')
		makedirs(path('cache/server/${version}'))
		copy(path('target/fman.rpm'), path('cache/server/${version}/fman.rpm'))
		_create_rpm_repo()
		files = upload_directory_contents(path('target/server/rpm'), 'rpm')
		create_cloudfront_invalidation(files)

def _create_rpm_repo():
	if exists(path('target/server')):
		rmtree(path('target/server'))
	_download_missing_files_from_aws('**/*.rpm', dest=path('cache/server'))
	try:
		copytree(path('cache/server'), path('target/server'))
	except FileNotFoundError:
		makedirs(path('target/server'))
	makedirs(path('target/server/rpm'), exist_ok=True)
	run(
		['createrepo_c', '-o', 'rpm', '--location-prefix', '..', '.'],
		check=True, cwd=(path('target/server'))
	)
	copy(path('src/build/rpm/fman.repo'), path('target/server/rpm'))
	copy(
		path('conf/linux/public.gpg-key'),
		path('target/server/rpm/public.gpg')
	)

def _download_missing_files_from_aws(pattern, dest):
	for file_path in list_files_on_s3():
		if not fnmatch(file_path, pattern):
			continue
		dest_path = join(dest, *file_path.split('/'))
		if not exists(dest_path):
			makedirs(dirname(dest_path), exist_ok=True)
			download_file_from_s3(file_path, dest_path)

def _run(*command):
	return run(command, stdout=PIPE, universal_newlines=True, check=True).stdout