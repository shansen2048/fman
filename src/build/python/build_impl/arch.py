from build_impl import upload_file, get_path_on_server, upload_installer_to_aws
from build_impl.linux import postprocess_exe, preset_gpg_passphrase
from fbs import path, SETTINGS
from fbs.cmdline import command
from fbs.freeze.arch import freeze_arch
from fbs.resources import copy_with_filtering
from os import makedirs
from os.path import exists, join, expanduser
from shutil import rmtree, copy
from subprocess import check_call, run, PIPE, DEVNULL

import hashlib
import os

@command
def freeze():
	freeze_arch()
	postprocess_exe()

@command
def sign_installer():
	# Prevent GPG from prompting us for the passphrase when signing:
	preset_gpg_passphrase()
	pkg_file = path('target/${installer}')
	check_call(
		['gpg', '--batch', '--yes', '-u', '0x%s!' % SETTINGS['gpg_key'],
		'--output', pkg_file + '.sig', '--detach-sig', pkg_file],
		stdout=DEVNULL
	)

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
	check_call([
		'repo-add', 'fman.db.tar.gz', pkg_file_versioned
	], cwd=repo_dir)
	# Ensure the permissions on the server are correct:
	check_call(['chmod', 'g-w', '-R', repo_dir])

def _upload_to_AUR():
	if exists(path('target/AUR')):
		rmtree(path('target/AUR'))
	makedirs(path('target/AUR'))
	env = dict(os.environ)
	env['GIT_SSH_COMMAND'] = 'ssh -i ' + SETTINGS['ssh_key']
	cwd = path('target/AUR')
	def git(*args):
		check_call(['git'] + list(args), cwd=cwd, env=env)
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
	pkgbuild = path('src/main/resources/arch-repo/PKGBUILD')
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
	srcinfo = path('src/main/resources/arch-repo/.SRCINFO')
	context['deps'] = \
		'\n\t'.join('depends = ' + dep for dep in SETTINGS['depends'])
	context['opt_deps'] = \
		'\n\t'.join('optdepends = ' + dep for dep in SETTINGS['depends_opt'])
	copy_with_filtering(srcinfo, dest_dir, context, files_to_filter=[srcinfo])

def _add_to_known_hosts(host):
	p = run(['ssh-keyscan', '-H', host], stdout=PIPE, stderr=PIPE)
	with open(expanduser('~/.ssh/known_hosts'), 'ab') as f:
		f.write(b'\n' + p.stdout)