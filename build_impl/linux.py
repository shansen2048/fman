from build_impl import run, path, generate_resources, copy_python_library, \
	OPTIONS, upload_file, run_on_server, get_path_on_server, run_pyinstaller, \
	copy_with_filtering, collectstatic
from os import makedirs
from os.path import exists, basename, join
from shutil import copytree, rmtree, copy
from time import time

def exe():
	run_pyinstaller()
	exclude = [
		path('src/main/resources/linux/' + file_name)
		for file_name in (
			'fman.desktop', 'fman.list', 'after-install.sh', 'update-fman',
			'fman', 'private.gpg-key', 'public.gpg-key', 'after-upgrade.sh'
		)
	]
	generate_resources(dest_dir=path('target/fman'), exclude=exclude)
	copy_python_library('send2trash', path('target/fman/Plugins/Core'))
	copy_python_library('ordered_set', path('target/fman/Plugins/Core'))

def deb():
	if exists(path('target/deb')):
		rmtree(path('target/deb'))
	copytree(path('target/fman'), path('target/deb/opt/fman'))
	for file_name, dest in (
		('fman.list', '/etc/apt/sources.list.d'),
		('fman.desktop', '/usr/share/applications'),
		('update-fman', '/usr/bin'), ('fman', '/etc/cron.daily')
	):
		to_copy = path('src/main/resources/linux/' + file_name)
		copy_with_filtering(
			to_copy, path('target/deb' + dest), files_to_filter=[to_copy]
		)
	for file_name in ('after-install.sh', 'after-upgrade.sh'):
		src_path = path('src/main/resources/linux/' + file_name)
		copy_with_filtering(
			src_path, path('target'), files_to_filter=[src_path]
		)
	run([
		'fpm', '-s', 'dir', '-t', 'deb', '-n', 'fman', '-v', OPTIONS['version'],
		'--description', 'A modern file manager for power users.',
		'-m', 'Michael Herrmann <michael@herrmann.io>',
		'--vendor', 'Michael Herrmann', '--url', 'https://fman.io',
		'--after-install', path('target/after-install.sh'),
		'--after-upgrade', path('target/after-upgrade.sh'),
		# Avoid warning "The postinst maintainerscript of the package fman seems
		# to use apt-key (provided by apt) without depending on gnupg or
		# gnupg2.":
		'-d', 'gnupg',
		'-p', _get_deb_path(), '-f', '-C', path('target/deb')
	])

def upload():
	tmp_dir_local = path('target/upload_%d' % time())
	makedirs(tmp_dir_local)
	deb_path = _get_deb_path()
	copy(deb_path, tmp_dir_local)
	copy(path('src/main/resources/linux/private.gpg-key'), tmp_dir_local)
	copy(path('src/main/resources/linux/public.gpg-key'), tmp_dir_local)
	_generate_reprepro_distributions_file(tmp_dir_local)
	upload_file(tmp_dir_local, '/tmp')
	tmp_dir_remote = '/tmp/' + basename(tmp_dir_local)
	try:
		run_on_server(
			'gpg --import "%s/private.gpg-key" "%s/public.gpg-key" || true' %
			(tmp_dir_remote, tmp_dir_remote)
		)
		deb_path_remote = tmp_dir_remote + '/' + basename(deb_path)
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

def _get_deb_path(architecture='amd64'):
	return path('target/fman_%s_%s.deb' % (OPTIONS['version'], architecture))