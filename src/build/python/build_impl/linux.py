from build_impl import copy_python_library
from fbs import path
from fbs.resources import copy_with_filtering, get_icons
from os import makedirs
from os.path import join, dirname
from shutil import copy, rmtree

FMAN_DESCRIPTION = \
	'A modern file manager for power users. Beautiful, fast and extensible'
FMAN_AUTHOR = 'Michael Herrmann'
FMAN_AUTHOR_EMAIL = 'michael+removethisifyouarehuman@herrmann.io'

def postprocess_exe():
	rmtree(path('${freeze_dir}/Plugins/Core/bin/mac'))
	rmtree(path('${freeze_dir}/Plugins/Core/bin/windows'))
	copy_python_library('send2trash', path('${freeze_dir}/Plugins/Core'))
	copy_python_library('ordered_set', path('${freeze_dir}/Plugins/Core'))

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