from build_impl import linux, run, OPTIONS, copy_with_filtering, upload_file, \
	get_path_on_server, upload_installer_to_aws
from build_impl.linux import FMAN_DESCRIPTION, FMAN_AUTHOR, FMAN_AUTHOR_EMAIL, \
	copy_linux_package_resources, copy_icons, remove_shared_libraries
from distutils.dir_util import copy_tree
from fbs.conf import path
from fbs.init import create_venv, install_requirements
from os import makedirs
from os.path import exists, join, expanduser
from shutil import rmtree, copytree, copy
from subprocess import Popen, PIPE, TimeoutExpired, CalledProcessError

import hashlib
import subprocess

_ARCH_DEPENDENCIES = ('qt5-base', 'p7zip')
_ARCH_OPT_DEPENDENCIES = ('qt5-svg',)
_PKG_FILE = path('target/fman.pkg.tar.xz')

def init():
	create_venv(system_site_packages=True)
	install_requirements(path('requirements/arch.txt'))

def exe():
	linux.exe()
	# fman normally ships with eg. libQt5Core.so.5. This loads other .so files,
	# if present, from /usr/lib. If those libraries are Qt libraries of a
	# different Qt version, errors occur.
	# For this reason, on systems with pacman, we don't include Qt. Instead, we
	# declare it as a dependency and leave it up to pacman to fetch it.
	remove_shared_libraries('libicudata.so.*', 'libQt*.so.*')

def pkg():
	if exists(path('target/arch-pkg')):
		rmtree(path('target/arch-pkg'))
	copytree(path('target/fman'), path('target/arch-pkg/opt/fman'))
	copy_linux_package_resources(path('target/arch-pkg'))
	copy(path('conf/linux/public.gpg-key'), path('target/arch-pkg/opt/fman'))
	copy_icons(path('target/arch-pkg'))
	# Avoid pacman warning "directory permissions differ" when installing:
	run(['chmod', 'g-w', '-R', path('target/arch-pkg')])
	version = OPTIONS['version']
	args = [
		'fpm', '-s', 'dir', '-t', 'pacman', '-n', 'fman',
		'-v', version,
		'--description', FMAN_DESCRIPTION,
		'-m', '%s <%s>' % (FMAN_AUTHOR, FMAN_AUTHOR_EMAIL),
		'--vendor', FMAN_AUTHOR,
		'--url', 'https://fman.io',
	]
	for dep in _ARCH_DEPENDENCIES:
		args.extend(['-d', dep])
	args.extend([
		'-p', _PKG_FILE,
		'-f', '-C', path('target/arch-pkg')
	])
	run(args)

def sign_pkg():
	gpg_pw = OPTIONS['gpg_pass']
	run([
		'gpg', '--batch', '--yes', '--passphrase', gpg_pw,
		'--import', path('conf/linux/private.gpg-key'),
		path('conf/linux/public.gpg-key')
		# The command fails if the key is already installed - ignore:
	], check_result=False)
	cmd = [
		'gpg', '--batch', '--yes', '--pinentry-mode', 'loopback',
		'--passphrase-fd', '0', '-u', '0x%s!' % OPTIONS['gpg_key'],
		'--output', _PKG_FILE + '.sig', '--detach-sig', _PKG_FILE
	]
	process = Popen(cmd, stdin=PIPE, universal_newlines=True)
	try:
		process.communicate(('%s\n' % gpg_pw) * 2, timeout=15)
	except TimeoutExpired:
		process.kill()
		stdout, stderr = process.communicate()
		raise CalledProcessError(process.returncode, cmd, stdout, stderr)

def repo():
	if exists(path('target/arch-repo')):
		rmtree(path('target/arch-repo'))
	repo_dir = path('target/arch-repo/arch')
	makedirs(repo_dir)
	pkg_file_versioned = 'fman-%s.pkg.tar.xz' % OPTIONS['version']
	copy(_PKG_FILE, join(repo_dir, pkg_file_versioned))
	copy(_PKG_FILE + '.sig', join(repo_dir, pkg_file_versioned + '.sig'))
	run([
		'repo-add', 'fman.db.tar.gz', pkg_file_versioned
	], cwd=repo_dir)
	# Ensure the permissions on the server are correct:
	run(['chmod', 'g-w', '-R', repo_dir])

def pkgbuild():
	with open(_PKG_FILE, 'rb') as f:
		sha256 = hashlib.sha256(f.read()).hexdigest()
	pkgbuild = path('src/main/resources/linux-AUR/PKGBUILD')
	context = {
		'author': FMAN_AUTHOR,
		'author_email': FMAN_AUTHOR_EMAIL,
		'version': OPTIONS['version'],
		'description': FMAN_DESCRIPTION,
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
	upload_file(path('target/arch-repo/arch'), get_path_on_server('updates'))
	if OPTIONS['release']:
		upload_installer_to_aws('fman.pkg.tar.xz')
		_publish_to_AUR()

def _publish_to_AUR():
	if exists(path('target/AUR')):
		rmtree(path('target/AUR'))
	makedirs(path('target/AUR'))
	env = {
		'GIT_SSH_COMMAND': 'ssh -i ' + OPTIONS['ssh_key']
	}
	cwd = path('target/AUR')
	def git(*args):
		run(['git'] + list(args), cwd=cwd, extra_env=env)
	_add_to_known_hosts('aur.archlinux.org')
	git('clone', 'ssh://aur@aur.archlinux.org/fman.git')
	copy_tree(path('target/pkgbuild'), path('target/AUR/fman'))
	cwd = path('target/AUR/fman')
	git('add', '-A')
	git('commit', '-m', 'Changes for fman ' + OPTIONS['version'])
	git('push', '-u', 'origin', 'master')

def _add_to_known_hosts(host):
	p = subprocess.run(['ssh-keyscan', '-H', host], stdout=PIPE, stderr=PIPE)
	with open(expanduser('~/.ssh/known_hosts'), 'ab') as f:
		f.write(b'\n' + p.stdout)