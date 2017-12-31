from build_impl import upload_file, get_path_on_server, upload_installer_to_aws
from build_impl.linux import FMAN_DESCRIPTION, FMAN_AUTHOR, FMAN_AUTHOR_EMAIL, \
	copy_linux_package_resources, copy_icons
from distutils.dir_util import copy_tree
from fbs import path, SETTINGS
from fbs.cmdline import command
from fbs.freeze.arch import freeze_arch
from fbs.resources import copy_with_filtering
from os import makedirs
from os.path import exists, join, expanduser
from shutil import rmtree, copytree, copy
from subprocess import run, Popen, PIPE, TimeoutExpired, CalledProcessError

import hashlib
import os

_ARCH_DEPENDENCIES = ('qt5-base', 'p7zip')
_ARCH_OPT_DEPENDENCIES = ('qt5-svg',)

@command
def exe():
	freeze_arch()

@command
def pkg():
	if exists(path('target/arch-pkg')):
		rmtree(path('target/arch-pkg'))
	copytree(path('${freeze_dir}'), path('target/arch-pkg/opt/fman'))
	copy_linux_package_resources(path('target/arch-pkg'))
	copy(path('conf/linux/public.gpg-key'), path('target/arch-pkg/opt/fman'))
	copy_icons(path('target/arch-pkg'))
	# Avoid pacman warning "directory permissions differ" when installing:
	run(['chmod', 'g-w', '-R', path('target/arch-pkg')], check=True)
	version = SETTINGS['version']
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
		'-p', path(SETTINGS['arch_pkg']),
		'-f', '-C', path('target/arch-pkg')
	])
	run(args, check=True)

@command
def sign_pkg():
	gpg_pw = SETTINGS['gpg_pass']
	run([
		'gpg', '--batch', '--yes', '--passphrase', gpg_pw,
		'--import', path('conf/linux/private.gpg-key'),
		path('conf/linux/public.gpg-key')
	]) # Don't check=True because the call fails if the key is already installed
	pkg_file = path(SETTINGS['arch_pkg'])
	cmd = [
		'gpg', '--batch', '--yes', '--pinentry-mode', 'loopback',
		'--passphrase-fd', '0', '-u', '0x%s!' % SETTINGS['gpg_key'],
		'--output', pkg_file + '.sig', '--detach-sig', pkg_file
	]
	process = Popen(cmd, stdin=PIPE, universal_newlines=True)
	try:
		process.communicate(('%s\n' % gpg_pw) * 2, timeout=15)
	except TimeoutExpired:
		process.kill()
		stdout, stderr = process.communicate()
		raise CalledProcessError(process.returncode, cmd, stdout, stderr)

@command
def repo():
	if exists(path('target/arch-repo')):
		rmtree(path('target/arch-repo'))
	repo_dir = path('target/arch-repo/arch')
	makedirs(repo_dir)
	pkg_file_versioned = 'fman-%s.pkg.tar.xz' % SETTINGS['version']
	pkg_file = path(SETTINGS['arch_pkg'])
	copy(pkg_file, join(repo_dir, pkg_file_versioned))
	copy(pkg_file + '.sig', join(repo_dir, pkg_file_versioned + '.sig'))
	run([
		'repo-add', 'fman.db.tar.gz', pkg_file_versioned
	], cwd=repo_dir, check=True)
	# Ensure the permissions on the server are correct:
	run(['chmod', 'g-w', '-R', repo_dir], check=True)

@command
def pkgbuild():
	with open(path(SETTINGS['arch_pkg']), 'rb') as f:
		sha256 = hashlib.sha256(f.read()).hexdigest()
	pkgbuild = path('src/main/resources/linux-AUR/PKGBUILD')
	context = {
		'author': FMAN_AUTHOR,
		'author_email': FMAN_AUTHOR_EMAIL,
		'version': SETTINGS['version'],
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

@command
def upload():
	upload_file(path('target/arch-repo/arch'), get_path_on_server('updates'))
	if SETTINGS['release']:
		upload_installer_to_aws('fman.pkg.tar.xz')
		_publish_to_AUR()

def _publish_to_AUR():
	if exists(path('target/AUR')):
		rmtree(path('target/AUR'))
	makedirs(path('target/AUR'))
	env = dict(os.environ)
	env['GIT_SSH_COMMAND'] = 'ssh -i ' + SETTINGS['ssh_key']
	cwd = path('target/AUR')
	def git(*args):
		run(['git'] + list(args), cwd=cwd, env=env, check=True)
	_add_to_known_hosts('aur.archlinux.org')
	git('clone', 'ssh://aur@aur.archlinux.org/fman.git')
	copy_tree(path('target/pkgbuild'), path('target/AUR/fman'))
	cwd = path('target/AUR/fman')
	git('add', '-A')
	git('commit', '-m', 'Changes for fman ' + SETTINGS['version'])
	git('push', '-u', 'origin', 'master')

def _add_to_known_hosts(host):
	p = run(['ssh-keyscan', '-H', host], stdout=PIPE, stderr=PIPE)
	with open(expanduser('~/.ssh/known_hosts'), 'ab') as f:
		f.write(b'\n' + p.stdout)