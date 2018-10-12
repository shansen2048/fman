from build_impl import upload_installer_to_aws
from build_impl.linux import postprocess_exe, copy_linux_package_resources, \
	copy_icons, FMAN_DESCRIPTION, FMAN_AUTHOR, FMAN_AUTHOR_EMAIL
from fbs import path, SETTINGS
from fbs.cmdline import command
from fbs.freeze.linux import freeze_linux
from os import remove
from os.path import exists, join
from shutil import rmtree, copytree
from subprocess import run, PIPE

import re

@command
def freeze():
	freeze_linux(extra_pyinstaller_args=[
		'--hidden-import', 'pgi.overrides.GObject',
		'--hidden-import', 'pgi.overrides.GLib',
		# Dependency of the Core plugin:
		'--hidden-import', 'pty'
	])
	# Force Fedora to use the system's Gnome libraries. This avoids warnings
	# when starting fman on the command line.
	remove(path('${freeze_dir}/libgio-2.0.so.0'))
	remove(path('${freeze_dir}/libglib-2.0.so.0'))
	postprocess_exe()

@command
def installer():
	dest_dir = path('target/rpm')
	if exists(dest_dir):
		rmtree(dest_dir)
	copytree(path('${freeze_dir}'), join(dest_dir, 'opt', 'fman'))
	copy_linux_package_resources(dest_dir)
	copy_icons(dest_dir)
	run([
		'fpm', '-s', 'dir', '-t', 'rpm', '-n', 'fman',
		'-v', SETTINGS['version'],
		'--description', FMAN_DESCRIPTION,
		'-m', '%s <%s>' % (FMAN_AUTHOR, FMAN_AUTHOR_EMAIL),
		'--vendor', FMAN_AUTHOR,
		'--url', 'https://fman.io',
		'-p', path('target/fman.rpm'),
		'-f', '-C', dest_dir
	], check=True)

@command
def sign_installer():
	# Prevent GPG from prompting us for the passphrase when signing:
	_preload_gpg_passphrase()
	run(['rpm', '--addsign', path('target/fman.rpm')])

@command
def upload():
	if SETTINGS['release']:
		upload_installer_to_aws('fman.rpm')

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

def _run(*command):
	return run(command, stdout=PIPE, universal_newlines=True, check=True).stdout