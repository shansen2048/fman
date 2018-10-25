from build_impl import check_output_decode, remove_if_exists, SETTINGS, \
	upload_installer_to_aws, upload_file, get_path_on_server
from build_impl.linux import postprocess_exe, preset_gpg_passphrase
from fbs import path
from fbs.cmdline import command
from fbs.freeze.ubuntu import freeze_ubuntu
from fbs.resources import copy_with_filtering
from os import makedirs, listdir
from os.path import join, exists
from shutil import rmtree
from subprocess import check_call

import re

@command
def freeze():
	freeze_ubuntu()
	postprocess_exe()
	# We're using Python library `pgi` instead of `gi`, `GObject` or other more
	# well-known alternatives. PyInstaller does not know how to handle this
	# properly and includes .so files it shouldn't include. In particular, we
	# use libgtk-3.so.0 via pgi. PyInstaller does *not* include that file. BUT
	# it does include some of its dependencies. When we then deploy fman to a
	# different Linux version, PyInstaller loads that distribution's
	# libgtk-3.so.0 but our copy of its dependencies, which fails. We thus
	# exclude the dependencies so that when fman runs on a different system,
	# PyInstaller loads the dependencies from that system:
	_remove_gtk_dependencies()

def _remove_gtk_dependencies():
	output = check_output_decode(
		'ldd /usr/lib/x86_64-linux-gnu/libgtk-3.so.0', shell=True
	)
	assert output.endswith('\n')
	for line in output.split('\n')[:-1]:
		if not '=>' in line:
			continue
		match = re.match('\t(?:(.*) => )?(.*) \(0x[0-9a-f]+\)', line)
		if not match:
			raise ValueError(repr(line))
		so_name, so_path = match.groups()
		if so_name and so_path:
			# libQt5Widgets.so.0 depends on libpng12.so.0. This file is present
			# on Ubuntu versions < 17.04. On 17.04 (and above?), libpng16.so.0
			# is used instead. We therefore need to keep libpng12.so.0 so fman
			# can run on Ubuntu 17.04+:
			if so_name != 'libpng12.so.0':
				remove_if_exists(path('${freeze_dir}/' + so_name))

@command
def upload():
	_generate_repo()
	updates_dir = get_path_on_server('updates/ubuntu')
	for f in listdir(path('target/upload')):
		upload_file(join(path('target/upload'), f), updates_dir)
	if SETTINGS['release']:
		upload_installer_to_aws('fman.deb')

def _generate_repo():
	if exists(path('target/repo')):
		rmtree(path('target/repo'))
	if exists(path('target/upload')):
		rmtree(path('target/upload'))
	makedirs(path('target/repo'))
	distr_file = path('src/main/resources/ubuntu-repo/distributions')
	copy_with_filtering(
		distr_file, path('target/repo'), files_to_filter=[distr_file]
	)
	preset_gpg_passphrase()
	check_call([
		'reprepro', '-b', path('target/upload'),
		'--confdir', path('target/repo'),
		'includedeb', 'stable', path('target/fman.deb')
	])