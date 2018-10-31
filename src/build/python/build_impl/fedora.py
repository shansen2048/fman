from build_impl import upload_installer_to_aws
from build_impl.aws import list_files_on_s3, download_file_from_s3, \
	upload_directory_contents, create_cloudfront_invalidation
from build_impl.linux import postprocess_exe, preset_gpg_passphrase
from fbs import path, SETTINGS
from fbs.cmdline import command
from fbs.freeze.fedora import freeze_fedora
from fnmatch import fnmatch
from os import makedirs
from os.path import exists, join, dirname
from shutil import rmtree, copytree, copy
from subprocess import check_call, DEVNULL

@command
def freeze():
	freeze_fedora()
	postprocess_exe()

@command
def sign_installer():
	# Prevent GPG from prompting us for the passphrase when signing:
	preset_gpg_passphrase()
	check_call(['rpm', '--addsign', path('target/fman.rpm')], stdout=DEVNULL)

@command
def upload():
	if SETTINGS['release']:
		upload_installer_to_aws('fman.rpm')
		makedirs(path('cache/server/${version}'))
		copy(path('target/fman.rpm'), path('cache/server/${version}/fman.rpm'))
		_create_rpm_repo()
		files = upload_directory_contents(path('target/server/rpm'), 'rpm')
		create_cloudfront_invalidation(files)

def _create_rpm_repo():
	if exists(path('target/server')):
		rmtree(path('target/server'))
	_download_missing_files_from_aws('**/*.rpm', dest=path('cache/server'))
	try:
		copytree(path('cache/server'), path('target/server'))
	except FileNotFoundError:
		makedirs(path('target/server'))
	makedirs(path('target/server/rpm'), exist_ok=True)
	check_call(
		['createrepo_c', '-o', 'rpm', '--location-prefix', '..', '.'],
		cwd=(path('target/server'))
	)
	copy(
		path('src/repo/fedora/fman.repo'),
		path('target/server/rpm')
	)
	copy(
		path('conf/linux/public.gpg-key'),
		path('target/server/rpm/public.gpg')
	)

def _download_missing_files_from_aws(pattern, dest):
	for file_path in list_files_on_s3():
		if not fnmatch(file_path, pattern):
			continue
		dest_path = join(dest, *file_path.split('/'))
		if not exists(dest_path):
			makedirs(dirname(dest_path), exist_ok=True)
			download_file_from_s3(file_path, dest_path)