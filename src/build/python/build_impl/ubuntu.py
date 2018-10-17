from build_impl import check_output_decode, remove_if_exists, SETTINGS, \
	upload_installer_to_aws, upload_file, run_on_server, get_path_on_server
from build_impl.linux import copy_linux_package_resources, copy_icons, \
	postprocess_exe
from fbs import path
from fbs.cmdline import command
from fbs.freeze.linux import freeze_linux
from fbs.resources import copy_with_filtering
from os import makedirs
from os.path import exists, join, basename
from shutil import rmtree, copytree, copy
from subprocess import run
from tempfile import TemporaryDirectory

import re

@command
def freeze():
	freeze_linux(extra_pyinstaller_args=[
		'--hidden-import', 'pgi.overrides.GObject',
		'--hidden-import', 'pgi.overrides.GLib',
		# Dependency of the Core plugin:
		'--hidden-import', 'pty'
	])
	postprocess_exe()
	# When we build on Ubuntu on 14.04 and run on 17.10, fman fails to start
	# with the following error:
	#
	#     This application failed to start because it could not find or load the
	#     Qt platform plugin "xcb" in "". Available platform plugins are:
	#     eglfs, linuxfb, minimal, minimalegl, offscreen, vnc, xcb.
	#
	# Interestingly, the error does not occur when building on Ubuntu 16.04.
	# The difference between the two build outputs seems to be
	# libgpg-error.so.0. Removing it fixes the problem:
	remove_if_exists(path('${freeze_dir}/libgpg-error.so.0'))
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
def installer():
	if exists(path('target/deb')):
		rmtree(path('target/deb'))
	copytree(path('${freeze_dir}'), path('target/deb/opt/fman'))
	copy_with_filtering(
		path('src/main/resources/linux-deb'), path('target/deb')
	)
	copy_linux_package_resources(path('target/deb'))
	copy_icons(path('target/deb'))
	run([
		'fpm', '-s', 'dir', '-t', 'deb', '-n', 'fman',
		'-v', SETTINGS['version'],
		'--description', SETTINGS['description'],
		'-m', '%s <%s>' % (SETTINGS['author'], SETTINGS['author_email']),
		'--vendor', SETTINGS['author'],
		'--url', 'https://fman.io',
		'-p', path('target/fman.deb'),
		'-f', '-C', path('target/deb')
	], check=True)

@command
def upload():
	_upload_deb()
	if SETTINGS['release']:
		upload_installer_to_aws('fman.deb')

def _upload_deb():
	# We supply the dir=... parameter to TemporaryDirectory for the following
	# reason: In the Ubuntu Docker build, upload_file(...) copies to /tmp.
	# Without the dir=... parameter, tmp_dir_local below would also lie in /tmp.
	# So upload_file(...) would try to copy the directory itself. This fails for
	# obvious reasons.
	with TemporaryDirectory(dir=path('target')) as tmp_dir_local:
		deb_name = _get_deb_name()
		copy(path('target/fman.deb'), join(tmp_dir_local, deb_name))
		copy(path('conf/linux/private.gpg-key'), tmp_dir_local)
		copy(path('conf/linux/public.gpg-key'), tmp_dir_local)
		copy(
			path('src/main/resources/linux-deb-upload/reprepro_no_pw_prompt.sh'),
			tmp_dir_local
		)
		_generate_reprepro_distributions_file(tmp_dir_local)
		upload_file(tmp_dir_local, '/tmp')
		tmp_dir_remote = '/tmp/' + basename(tmp_dir_local)
	try:
		gpg_pass = SETTINGS['gpg_pass']
		run_on_server(
			'gpg --batch --yes --passphrase %s --import "%s/private.gpg-key" '
			'"%s/public.gpg-key" || true' %
			(gpg_pass, tmp_dir_remote, tmp_dir_remote)
		)
		deb_path_remote = tmp_dir_remote + '/' + deb_name
		updates_dir = get_path_on_server('updates/ubuntu')
		# Run reprepro on a temporary directory first, to not screw up its state
		# if something goes wrong:
		run_on_server('cp -r "%s" "%s"' % (updates_dir, tmp_dir_remote))
		tmp_updates_dir = tmp_dir_remote + '/ubuntu'
		run_on_server(
			'%s/reprepro_no_pw_prompt.sh "%s" "%s" "%s/reprepro/conf" '
			'includedeb stable "%s"' % (
				tmp_dir_remote, gpg_pass, tmp_updates_dir,
				tmp_dir_remote, deb_path_remote
			)
		)
		mv = lambda src, dst: run_on_server('mv "%s" "%s"' % (src, dst))
		updates_dir_backup = tmp_dir_remote + '/ubuntu_old'
		mv(updates_dir, updates_dir_backup)
		try:
			mv(tmp_updates_dir, updates_dir)
		except Exception:
			mv(updates_dir_backup, updates_dir)
	finally:
		run_on_server('rm -rf "%s"' % tmp_dir_remote)

def _get_deb_name(architecture='amd64'):
	return 'fman_%s_%s.deb' % (SETTINGS['version'], architecture)

def _generate_reprepro_distributions_file(dest_dir):
	conf_dir = join(dest_dir, 'reprepro', 'conf')
	makedirs(conf_dir)
	with open(join(conf_dir, 'distributions'), 'w') as f:
		f.write('\n'.join([
			'Origin: fman',
			'Label: fman',
			'Codename: stable',
			'Architectures: amd64',
			'Components: main',
			'Description: ' + SETTINGS['description'],
			'SignWith: ' + SETTINGS['gpg_key']
		]) + '\n\n')