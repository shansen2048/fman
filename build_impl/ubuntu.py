from build_impl import linux, path, check_output_decode, remove_if_exists, \
	copy_with_filtering, run, OPTIONS, upload_installer_to_aws, upload_file, \
	run_on_server, get_path_on_server
from build_impl.init import create_venv, install_requirements, install_sip, \
	install_pyqt
from build_impl.linux import FMAN_DESCRIPTION, FMAN_AUTHOR, FMAN_AUTHOR_EMAIL, \
	copy_linux_package_resources, copy_icons
from os import makedirs
from os.path import exists, join, basename
from shutil import rmtree, copytree, copy
from time import time

import re

def init():
	create_venv()
	install_sip()
	install_pyqt()
	install_requirements(path('requirements/ubuntu.txt'))

def exe():
	linux.exe()
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
			remove_if_exists(path('target/fman/' + so_name))

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
		files_to_filter=[deb_resource('/etc/apt/sources.list.d/fman.list')]
	)
	copy_linux_package_resources(path('target/deb'))
	copy_with_filtering(
		path('src/main/resources/linux-deb-config'), path('target/deb-config'),
		files_to_filter=[
			path('src/main/resources/linux-deb-config/after-install.sh')
		]
	)
	copy(path('conf/linux/public.gpg-key'), path('target/deb/opt/fman'))
	copy_icons(path('target/deb'))
	run([
		'fpm', '-s', 'dir', '-t', 'deb', '-n', 'fman',
		'-v', OPTIONS['version'],
		'--description', FMAN_DESCRIPTION,
		'-m', '%s <%s>' % (FMAN_AUTHOR, FMAN_AUTHOR_EMAIL),
		'--vendor', FMAN_AUTHOR,
		'--url', 'https://fman.io',
		'--after-install', path('target/deb-config/after-install.sh'),
		'--after-upgrade', path('src/main/resources/fpm/after-upgrade.sh'),
		# Avoid warning "The postinst maintainerscript of the package fman seems
		# to use apt-key (provided by apt) without depending on gnupg or
		# gnupg2.":
		'-d', 'gnupg',
		'-p', path('target/fman.deb'),
		'-f', '-C', path('target/deb')
	])
	run(['chmod', 'g-r', '-R', path('target/deb')])

def upload():
	_upload_deb()
	if OPTIONS['release']:
		upload_installer_to_aws('fman.deb')

def _upload_deb():
	tmp_dir_local = path('target/upload_%d' % time())
	makedirs(tmp_dir_local)
	deb_name = _get_deb_name()
	copy(path('target/fman.deb'), join(tmp_dir_local, deb_name))
	copy(path('conf/linux/private.gpg-key'), tmp_dir_local)
	copy(path('conf/linux/public.gpg-key'), tmp_dir_local)
	_generate_reprepro_distributions_file(tmp_dir_local)
	upload_file(tmp_dir_local, '/tmp')
	tmp_dir_remote = '/tmp/' + basename(tmp_dir_local)
	try:
		run_on_server(
			'gpg --batch --yes --passphrase %s --import "%s/private.gpg-key" '
			'"%s/public.gpg-key" || true' %
			(OPTIONS['gpg_pass'], tmp_dir_remote, tmp_dir_remote)
		)
		deb_path_remote = tmp_dir_remote + '/' + deb_name
		run_on_server(
			'reprepro --ask-passphrase -b "%s" --confdir %s/reprepro/conf '
			'includedeb stable "%s"' % (
				get_path_on_server('updates/ubuntu'), tmp_dir_remote,
				deb_path_remote
			)
		)
	finally:
		run_on_server('rm -rf "%s"' % tmp_dir_remote)

def _get_deb_name(architecture='amd64'):
	return 'fman_%s_%s.deb' % (OPTIONS['version'], architecture)

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
			'Description: ' + FMAN_DESCRIPTION,
			'SignWith: ' + OPTIONS['gpg_key']
		]) + '\n\n')