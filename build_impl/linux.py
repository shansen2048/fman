from build_impl import run, path, generate_resources, copy_python_library, \
	OPTIONS, upload_file, run_on_server, get_path_on_server, run_pyinstaller, \
	copy_with_filtering, collectstatic, check_output_decode, get_icons, \
	upload_installer_to_aws
from distutils.dir_util import copy_tree
from glob import glob
from os import makedirs, remove, rename
from os.path import exists, basename, join, dirname
from shutil import copytree, rmtree, copy
from time import time

import hashlib
import re

_FMAN_DESCRIPTION = \
	'A modern file manager for power users. Beautiful, fast and extensible'
_FMAN_AUTHOR = 'Michael Herrmann'
_FMAN_AUTHOR_EMAIL = 'michael+removethisifyouarehuman@herrmann.io'

_ARCH_DEPENDENCIES = ('qt5-base', 'openssl')
_ARCH_OPT_DEPENDENCIES = ('qt5-svg',)

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
	remove(path('target/fman/libdrm.so.2'))
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
		files_to_filter=[deb_resource('/etc/apt/sources.list.d/fman.list')]
	)
	_copy_linux_package_resources(path('target/deb'))
	copy_with_filtering(
		path('src/main/resources/linux-deb-config'), path('target/deb-config'),
		files_to_filter=[
			path('src/main/resources/linux-deb-config/after-install.sh')
		]
	)
	copy(path('conf/linux/public.gpg-key'), path('target/deb/opt/fman'))
	_copy_icons(path('target/deb'))
	run([
		'fpm', '-s', 'dir', '-t', 'deb', '-n', 'fman',
		'-v', OPTIONS['version'],
		'--description', _FMAN_DESCRIPTION,
		'-m', '%s <%s>' % (_FMAN_AUTHOR, _FMAN_AUTHOR_EMAIL),
		'--vendor', _FMAN_AUTHOR,
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

def _copy_linux_package_resources(root_path):
	source_dir = 'src/main/resources/linux-package'
	copy_with_filtering(
		path('src/main/resources/linux-package'), root_path,
		files_to_filter=[
			path(source_dir + '/usr/bin/fman'),
			path(source_dir + '/usr/share/applications/fman.desktop')
		]
	)

def _copy_icons(root_path):
	icons_root = join(root_path, 'usr', 'share', 'icons', 'hicolor')
	makedirs(icons_root)
	for size, icon_path in get_icons():
		dest_path = join(icons_root, '%dx%d' % (size, size), 'apps', 'fman.png')
		makedirs(dirname(dest_path))
		copy(icon_path, dest_path)

def arch():
	pkg_file = _arch_pkg()
	_sign_arch_pkg(pkg_file)
	_arch_repo(pkg_file)
	_pkgbuild(pkg_file)

def _arch_pkg():
	if exists(path('target/arch-pkg')):
		rmtree(path('target/arch-pkg'))
	copytree(path('target/fman'), path('target/arch-pkg/opt/fman'))
	_remove_libs_declared_as_pacman_dependencies()
	_copy_linux_package_resources(path('target/arch-pkg'))
	copy(path('conf/linux/public.gpg-key'), path('target/arch-pkg/opt/fman'))
	_copy_icons(path('target/arch-pkg'))
	# Avoid pacman warning "directory permissions differ" when installing:
	run(['chmod', 'g-w', '-R', path('target/arch-pkg')])
	version = OPTIONS['version']
	pkg_file = path('target/fman.pkg.tar.xz')
	run([
		'fpm', '-s', 'dir', '-t', 'pacman', '-n', 'fman',
		'-v', version,
		'--description', _FMAN_DESCRIPTION,
		'-m', '%s <%s>' % (_FMAN_AUTHOR, _FMAN_AUTHOR_EMAIL),
		'--vendor', _FMAN_AUTHOR,
		'--url', 'https://fman.io',
		'-d', 'qt5-base', '-d', 'openssl',
		'-p', pkg_file,
		'-f', '-C', path('target/arch-pkg')
	])
	return pkg_file

def _remove_libs_declared_as_pacman_dependencies():
	# fman normally ships with eg. libQt5Core.so.5. This loads other .so files,
	# if present, from /usr/lib. If those libraries are Qt libraries of a
	# different Qt version, errors occur.
	# For this reason, on systems with pacman, we don't include Qt. Instead, we
	# declare it as a dependency and leave it up to pacman to fetch it.
	for qt_lib in glob(path('target/arch-pkg/opt/fman/libQt*.so.*')):
		remove(qt_lib)
	# We also declare 'openssl' as a dependency. Remove its .so files:
	remove(path('target/arch-pkg/opt/fman/libcrypto.so.1.0.0'))
	remove(path('target/arch-pkg/opt/fman/libssl.so.1.0.0'))

def _sign_arch_pkg(pkg_file):
	run([
		'gpg', '--import',
		path('conf/linux/private.gpg-key'),
		path('conf/linux/public.gpg-key')
	# The command fails if the key is already installed - ignore:
	], check_result=False)
	run([
		'gpg', '--yes', '-u', '0x%s!' % OPTIONS['gpg_key'],
		'--output', pkg_file + '.sig', '--detach-sig', pkg_file
	])

def _arch_repo(pkg_file):
	if exists(path('target/arch-repo')):
		rmtree(path('target/arch-repo'))
	repo_dir = path('target/arch-repo/arch')
	makedirs(repo_dir)
	pkg_file_versioned = 'fman-%s.pkg.tar.xz' % OPTIONS['version']
	copy(pkg_file, join(repo_dir, pkg_file_versioned))
	copy(pkg_file + '.sig', join(repo_dir, pkg_file_versioned + '.sig'))
	run([
		path('bin/linux/repo-add'), 'fman.db.tar.gz', pkg_file_versioned
	], cwd=repo_dir)
	# Ensure the permissions on the server are correct:
	run(['chmod', 'g-w', '-R', repo_dir])

def _pkgbuild(pkg_file):
	with open(pkg_file, 'rb') as f:
		sha256 = hashlib.sha256(f.read()).hexdigest()
	pkgbuild = path('src/main/resources/linux-AUR/PKGBUILD')
	context = {
		'author': _FMAN_AUTHOR,
		'author_email': _FMAN_AUTHOR_EMAIL,
		'version': OPTIONS['version'],
		'description': _FMAN_DESCRIPTION,
		'deps': ' '.join(map(repr, _ARCH_DEPENDENCIES)),
		'opt_deps': ' '.join(map(repr, _ARCH_OPT_DEPENDENCIES)),
		'sha256': sha256
	}
	copy_with_filtering(
		pkgbuild, path('target/pkgbuild'), context, files_to_filter=[pkgbuild]
	)
	srcinfo = path('src/main/resources/linux-AUR/.SRCINFO')
	context['deps'] = \
		'\n\t'.join('depends = ' + dep for dep in _ARCH_DEPENDENCIES)
	context['opt_deps'] = \
		'\n\t'.join('optdepends = ' + dep for dep in _ARCH_OPT_DEPENDENCIES)
	copy_with_filtering(
		srcinfo, path('target/pkgbuild'), context, files_to_filter=[srcinfo]
	)

def upload():
	_upload_deb()
	_upload_arch()
	if OPTIONS['release']:
		upload_installer_to_aws('fman.deb')
		upload_installer_to_aws('fman.pkg.tar.xz')
		_publish_to_AUR()

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
		collectstatic()
	finally:
		run_on_server('rm -rf "%s"' % tmp_dir_remote)

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
			'Description: ' + _FMAN_DESCRIPTION,
			'SignWith: ' + OPTIONS['gpg_key']
		]) + '\n\n')

def _get_deb_name(architecture='amd64'):
	return 'fman_%s_%s.deb' % (OPTIONS['version'], architecture)

def _upload_arch():
	upload_file(path('target/arch-repo/arch'), get_path_on_server('updates'))

def _publish_to_AUR():
	if exists(path('target/AUR')):
		rmtree(path('target/AUR'))
	makedirs(path('target/AUR'))
	run(
		['git', 'clone', 'ssh://aur@aur.archlinux.org/fman.git'],
		cwd=path('target/AUR')
	)
	copy_tree(path('target/pkgbuild'), path('target/AUR/fman'))
	git = lambda *args: run(['git'] + list(args), cwd=path('target/AUR/fman'))
	git('add', '-A')
	git('commit', '-m', 'Changes for fman ' + OPTIONS['version'])
	git('push', '-u', 'origin', 'master')