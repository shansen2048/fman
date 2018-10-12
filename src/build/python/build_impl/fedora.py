from build_impl.linux import postprocess_exe, copy_linux_package_resources, \
	copy_icons, FMAN_DESCRIPTION, FMAN_AUTHOR, FMAN_AUTHOR_EMAIL
from fbs import path, SETTINGS
from fbs.cmdline import command
from fbs.freeze.linux import freeze_linux
from os import remove
from os.path import exists, join
from shutil import rmtree, copytree
from subprocess import run

@command
def freeze():
	freeze_linux(extra_pyinstaller_args=[
		'--hidden-import', 'pgi.overrides.GObject',
		'--hidden-import', 'pgi.overrides.GLib',
		# Dependency of the Core plugin:
		'--hidden-import', 'pty'
	])
	# Force Fedora to use the system's Gnome libraries. This avoids warnings
	# when starting fman on the command line.
	remove(path('${freeze_dir}/libgio-2.0.so.0'))
	remove(path('${freeze_dir}/libglib-2.0.so.0'))
	postprocess_exe()

@command
def installer():
	dest_dir = path('target/rpm')
	if exists(dest_dir):
		rmtree(dest_dir)
	copytree(path('${freeze_dir}'), join(dest_dir, 'opt', 'fman'))
	copy_linux_package_resources(dest_dir)
	copy_icons(dest_dir)
	run([
		'fpm', '-s', 'dir', '-t', 'rpm', '-n', 'fman',
		'-v', SETTINGS['version'],
		'--description', FMAN_DESCRIPTION,
		'-m', '%s <%s>' % (FMAN_AUTHOR, FMAN_AUTHOR_EMAIL),
		'--vendor', FMAN_AUTHOR,
		'--url', 'https://fman.io',
		'-p', path('target/fman.rpm'),
		'-f', '-C', dest_dir
	], check=True)