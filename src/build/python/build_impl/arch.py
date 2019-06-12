from build_impl import upload_file, get_path_on_server, upload_installer_to_aws
from build_impl.linux import postprocess_exe
from fbs import path, SETTINGS
from fbs.cmdline import command
from fbs.freeze.arch import freeze_arch
from fbs.repo.arch import create_repo_arch

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