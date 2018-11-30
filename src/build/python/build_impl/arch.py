from build_impl import upload_file, get_path_on_server, upload_installer_to_aws
from build_impl.linux import postprocess_exe
from fbs import path, SETTINGS
from fbs.cmdline import command
from fbs.freeze.arch import freeze_arch
from fbs.repo.arch import create_repo_arch
from fbs.resources import copy_with_filtering
from os import makedirs
from os.path import exists, expanduser
from shutil import rmtree
from subprocess import check_call, run, PIPE

import hashlib
import os

@command
def freeze():
	freeze_arch()
	postprocess_exe()

@command
def upload():
	create_repo_arch()
	upload_file(
		path('target/repo'), get_path_on_server('updates'), dest_name='arch'
	)
	if SETTINGS['release']:
		upload_installer_to_aws('fman.pkg.tar.xz')
		_upload_to_AUR()

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
	pkgbuild = path('src/repo/arch/PKGBUILD')
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
	srcinfo = path('src/repo/arch/.SRCINFO')
	context['deps'] = \
		'\n\t'.join('depends = ' + dep for dep in SETTINGS['depends'])
	context['opt_deps'] = \
		'\n\t'.join('optdepends = ' + dep for dep in SETTINGS['depends_opt'])
	copy_with_filtering(srcinfo, dest_dir, context, files_to_filter=[srcinfo])

def _add_to_known_hosts(host):
	p = run(['ssh-keyscan', '-H', host], stdout=PIPE, stderr=PIPE)
	with open(expanduser('~/.ssh/known_hosts'), 'ab') as f:
		f.write(b'\n' + p.stdout)