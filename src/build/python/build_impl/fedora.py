from build_impl import upload_installer_to_aws
from build_impl.aws import upload_directory_contents, \
	create_cloudfront_invalidation
from build_impl.linux import postprocess_exe
from fbs import path, SETTINGS
from fbs.cmdline import command
from fbs.freeze.fedora import freeze_fedora
from fbs.repo.fedora import create_repo_fedora
from os import makedirs
from os.path import exists
from shutil import rmtree, copy, copytree

@command
def freeze():
	freeze_fedora()
	postprocess_exe()

@command
def upload():
	_create_rpm_repo()
	if SETTINGS['release']:
		upload_installer_to_aws('fman.rpm')
		files = upload_directory_contents(path('target/upload'), 'rpm')
		create_cloudfront_invalidation(files)

def _create_rpm_repo():
	if exists(path('target/upload')):
		rmtree(path('target/upload'))
	create_repo_fedora()
	# Convert to fman's directory structure:
	makedirs(path('target/upload'))
	copytree(path('target/repo/repodata'), path('target/upload/repodata'))
	copy(path('target/repo/fman.repo'), path('target/upload'))
	copy(
		path('src/sign/linux/public-key.gpg'), path('target/upload/public.gpg')
	)