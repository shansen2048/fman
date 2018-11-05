from build_impl import upload_installer_to_aws
from build_impl.aws import upload_directory_contents, \
	create_cloudfront_invalidation
from build_impl.linux import postprocess_exe, preset_gpg_passphrase
from fbs import path, SETTINGS
from fbs.cmdline import command
from fbs.freeze.fedora import freeze_fedora
from os import makedirs
from os.path import exists
from shutil import rmtree, copy
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
	_create_rpm_repo()
	if SETTINGS['release']:
		upload_installer_to_aws('fman.rpm')
		files = upload_directory_contents(path('target/upload/rpm'), 'rpm')
		create_cloudfront_invalidation(files)

def _create_rpm_repo():
	if exists(path('target/upload')):
		rmtree(path('target/upload'))
	makedirs(path('target/upload/${version}'))
	copy(path('target/fman.rpm'), path('target/upload/${version}/fman.rpm'))
	makedirs(path('target/upload/rpm'))
	check_call(
		['createrepo_c', '-o', 'rpm', '-u', 'https://download.fman.io', '.'],
		cwd=(path('target/upload'))
	)
	copy(
		path('src/repo/fedora/fman.repo'),
		path('target/upload/rpm')
	)
	copy(
		path('conf/linux/public.gpg-key'),
		path('target/upload/rpm/public.gpg')
	)