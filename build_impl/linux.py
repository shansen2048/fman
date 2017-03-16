from build_impl import run, path, generate_resources, copy_python_library, \
	OPTIONS, upload_file, run_on_server, get_path_on_server, run_pyinstaller, \
	copy_with_filtering, collectstatic, check_output_decode, get_icons, \
	upload_installer_to_aws
from os import makedirs, remove, rename
from os.path import exists, basename, join, dirname
from shutil import copytree, rmtree, copy
from time import time

import re

def exe():
	run_pyinstaller()
	# For some reason, PyInstaller packages libstdc++.so.6 even though it is
	# available on most Linux distributions. If we include it and run fman on a
	# different Ubuntu version, then Popen(...) calls fail with errors
	# "GLIBCXX_... not found" or "CXXABI_..." not found. So ensure we don't
	# package the file, so that the respective system's compatible version is
	# used:
	remove(path('target/fman/libstdc++.so.6'))
	remove(path('target/fman/libtinfo.so.5'))
	remove(path('target/fman/libreadline.so.6'))
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
	generate_resources(dest_dir=path('target/fman'))
	copy_python_library('send2trash', path('target/fman/Plugins/Core'))
	copy_python_library('ordered_set', path('target/fman/Plugins/Core'))

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
			try:
				remove(path('target/fman/' + so_name))
			except FileNotFoundError:
				pass

def deb():
	if exists(path('target/deb')):
		rmtree(path('target/deb'))
	if exists(path('target/deb-config')):
		rmtree(path('target/deb-config'))
	copytree(path('target/fman'), path('target/deb/opt/fman'))
	deb_resource = \
		lambda relpath: path('src/main/resources/linux-deb' + relpath)
	copy_with_filtering(
		path('src/main/resources/linux-deb'), path('target/deb'),
		files_to_filter=[
			deb_resource('/etc/apt/sources.list.d/fman.list'),
			deb_resource('/usr/share/applications/fman.desktop'),
			deb_resource('/usr/bin/fman')
		]
	)
	copy_with_filtering(
		path('src/main/resources/linux-deb-config'), path('target/deb-config'),
		files_to_filter=[
			path('src/main/resources/linux-deb-config/after-install.sh')
		]
	)
	icons_root = path('target/deb/usr/share/icons/hicolor')
	makedirs(icons_root)
	for size, icon_path in get_icons():
		dest_path = join(icons_root, '%dx%d' % (size, size), 'apps', 'fman.png')
		makedirs(dirname(dest_path))
		copy(icon_path, dest_path)
	run([
		'fpm', '-s', 'dir', '-t', 'deb', '-n', 'fman', '-v', OPTIONS['version'],
		'--description', 'A modern file manager for power users.',
		'-m', 'Michael Herrmann <michael@herrmann.io>',
		'--vendor', 'Michael Herrmann', '--url', 'https://fman.io',
		'--after-install', path('target/deb-config/after-install.sh'),
		'--after-upgrade', path('target/deb-config/after-upgrade.sh'),
		# Avoid warning "The postinst maintainerscript of the package fman seems
		# to use apt-key (provided by apt) without depending on gnupg or
		# gnupg2.":
		'-d', 'gnupg',
		'-p', path('target/fman.deb'), '-f', '-C', path('target/deb')
	])
	run(['chmod', 'g-r', '-R', path('target/deb')])

def upload():
	tmp_dir_local = path('target/upload_%d' % time())
	makedirs(tmp_dir_local)
	deb_name = _get_deb_name()
	copy(path('target/fman.deb'), join(tmp_dir_local, deb_name))
	copy(path('target/deb-config/private.gpg-key'), tmp_dir_local)
	copy(path('target/deb-config/public.gpg-key'), tmp_dir_local)
	_generate_reprepro_distributions_file(tmp_dir_local)
	upload_file(tmp_dir_local, '/tmp')
	tmp_dir_remote = '/tmp/' + basename(tmp_dir_local)
	try:
		run_on_server(
			'gpg --import "%s/private.gpg-key" "%s/public.gpg-key" || true' %
			(tmp_dir_remote, tmp_dir_remote)
		)
		deb_path_remote = tmp_dir_remote + '/' + deb_name
		run_on_server(
			'reprepro --ask-passphrase -b "%s" --confdir %s/reprepro/conf '
			'includedeb stable "%s"' % (
				get_path_on_server('updates/ubuntu'), tmp_dir_remote,
				deb_path_remote
			)
		)
		downloads_dir = get_path_on_server('downloads')
		run_on_server(
			'mkdir -p "%s" && mv "%s" "%s/fman.deb"' % (
				downloads_dir, deb_path_remote, downloads_dir
			)
		)
		collectstatic()
	finally:
		run_on_server('rm -rf "%s"' % tmp_dir_remote)
	if OPTIONS['release']:
		upload_installer_to_aws('fman.deb')

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
			'Description: A modern file manager for power users.',
			'SignWith: ' + OPTIONS['gpg_key']
		]) + '\n\n')

def _get_deb_name(architecture='amd64'):
	return 'fman_%s_%s.deb' % (OPTIONS['version'], architecture)