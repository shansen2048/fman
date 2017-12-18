from build_impl import generate_resources, copy_python_library, \
	run_pyinstaller, copy_with_filtering, get_icons
from fbs.conf import path
from glob import glob
from os import makedirs, remove
from os.path import join, dirname
from shutil import copy

FMAN_DESCRIPTION = \
	'A modern file manager for power users. Beautiful, fast and extensible'
FMAN_AUTHOR = 'Michael Herrmann'
FMAN_AUTHOR_EMAIL = 'michael+removethisifyouarehuman@herrmann.io'

def exe():
	run_pyinstaller()
	generate_resources(dest_dir=path('target/fman'))
	copy(path('src/main/icons/Icon.ico'), path('target/fman'))
	copy_python_library('send2trash', path('target/fman/Plugins/Core'))
	copy_python_library('ordered_set', path('target/fman/Plugins/Core'))
	# For some reason, PyInstaller packages libstdc++.so.6 even though it is
	# available on most Linux distributions. If we include it and run fman on a
	# different Ubuntu version, then Popen(...) calls fail with errors
	# "GLIBCXX_... not found" or "CXXABI_..." not found. So ensure we don't
	# package the file, so that the respective system's compatible version is
	# used:
	remove_shared_libraries(
		'libstdc++.so.*', 'libtinfo.so.*', 'libreadline.so.*', 'libdrm.so.*'
	)

def remove_shared_libraries(*filename_patterns):
	for pattern in filename_patterns:
		for file_path in glob(path('target/fman/' + pattern)):
			remove(file_path)

def copy_linux_package_resources(root_path):
	source_dir = 'src/main/resources/linux-package'
	copy_with_filtering(
		path('src/main/resources/linux-package'), root_path,
		files_to_filter=[
			path(source_dir + '/usr/bin/fman'),
			path(source_dir + '/usr/share/applications/fman.desktop')
		]
	)

def copy_icons(root_path):
	icons_root = join(root_path, 'usr', 'share', 'icons', 'hicolor')
	makedirs(icons_root)
	for size, icon_path in get_icons():
		dest_path = join(icons_root, '%dx%d' % (size, size), 'apps', 'fman.png')
		makedirs(dirname(dest_path))
		copy(icon_path, dest_path)