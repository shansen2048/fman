from build_impl import upload_file, get_path_on_server, upload_installer_to_aws
from build_impl.linux import postprocess_exe
from fbs import path, SETTINGS
from fbs.cmdline import command
from fbs.freeze.linux import freeze_linux
from fbs.resources import copy_with_filtering
from os import makedirs
from os.path import exists, join, expanduser
from shutil import rmtree, copy
from subprocess import run, Popen, PIPE, TimeoutExpired, CalledProcessError

import hashlib
import os

@command
def freeze():
	freeze_linux(extra_pyinstaller_args=[
		# Dependency of the Core plugin:
		'--hidden-import', 'pty'
	])
	postprocess_exe()

@command
def sign_installer():
	gpg_pw = SETTINGS['gpg_pass']
	run([
		'gpg', '--batch', '--yes', '--passphrase', gpg_pw,
		'--import', path('conf/linux/private.gpg-key'),
		path('conf/linux/public.gpg-key')
	]) # Don't check=True because the call fails if the key is already installed
	pkg_file = path('target/${installer}')
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
def upload():
	_generate_repo()
	upload_file(path('target/arch-repo/arch'), get_path_on_server('updates'))
	if SETTINGS['release']:
		upload_installer_to_aws('fman.pkg.tar.xz')
		_upload_to_AUR()

def _generate_repo():
	if exists(path('target/arch-repo')):
		rmtree(path('target/arch-repo'))
	repo_dir = path('target/arch-repo/arch')
	makedirs(repo_dir)
	pkg_file_versioned = 'fman-%s.pkg.tar.xz' % SETTINGS['version']
	pkg_file = path('target/${installer}')
	copy(pkg_file, join(repo_dir, pkg_file_versioned))
	copy(pkg_file + '.sig', join(repo_dir, pkg_file_versioned + '.sig'))
	run([
		'repo-add', 'fman.db.tar.gz', pkg_file_versioned
	], cwd=repo_dir, check=True)
	# Ensure the permissions on the server are correct:
	run(['chmod', 'g-w', '-R', repo_dir], check=True)

def _upload_to_AUR():
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
	_generate_pkgbuild(path('target/AUR/fman'))
	cwd = path('target/AUR/fman')
	git('add', '-A')
	git('commit', '-m', 'Changes for fman ' + SETTINGS['version'])
	git('push', '-u', 'origin', 'master')

def _generate_pkgbuild(dest_dir):
	with open(path('target/${installer}'), 'rb') as f:
		sha256 = hashlib.sha256(f.read()).hexdigest()
	pkgbuild = path('src/main/resources/linux-AUR/PKGBUILD')
	context = {
		'author': SETTINGS['author'],
		'author_email': SETTINGS['author_email'],
		'version': SETTINGS['version'],
		'description': SETTINGS['description'],
		'deps': ' '.join(map(repr, SETTINGS['depends'])),
		'opt_deps': ' '.join(map(repr, SETTINGS['depends_opt'])),
		'sha256': sha256
	}
	copy_with_filtering(pkgbuild, dest_dir, context, files_to_filter=[pkgbuild])
	srcinfo = path('src/main/resources/linux-AUR/.SRCINFO')
	context['deps'] = \
		'\n\t'.join('depends = ' + dep for dep in SETTINGS['depends'])
	context['opt_deps'] = \
		'\n\t'.join('optdepends = ' + dep for dep in SETTINGS['depends_opt'])
	copy_with_filtering(srcinfo, dest_dir, context, files_to_filter=[srcinfo])

def _add_to_known_hosts(host):
	p = run(['ssh-keyscan', '-H', host], stdout=PIPE, stderr=PIPE)
	with open(expanduser('~/.ssh/known_hosts'), 'ab') as f:
		f.write(b'\n' + p.stdout)