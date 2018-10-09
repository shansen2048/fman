from build_impl.linux import postprocess_exe
from fbs import path
from fbs.cmdline import command
from fbs.freeze.linux import freeze_linux
from os import remove

@command
def exe():
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