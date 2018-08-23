from build_impl import copy_python_library
from fbs import path
from fbs.resources import copy_with_filtering, get_icons
from os import makedirs, remove
from os.path import join, dirname
from shutil import copy, rmtree

FMAN_DESCRIPTION = \
	'A modern file manager for power users. Beautiful, fast and extensible'
FMAN_AUTHOR = 'Michael Herrmann'
FMAN_AUTHOR_EMAIL = 'michael+removethisifyouarehuman@herrmann.io'

def postprocess_exe():
	rmtree(path('${core_plugin_in_freeze_dir}/bin/mac'))
	rmtree(path('${core_plugin_in_freeze_dir}/bin/windows'))
	# Roboto Bold is only used on Windows. For reasons not yet known, loading
	# fonts sometimes fails. (A known case is that Open Sans fails to load on
	# some user's Windows systems - see fman issue #480). Remove the unused font
	# to avoid potential problems, improve startup performance and decrease
	# fman's download size.
	# (Also note that a more elegant solution would be to only place
	# Open Sans.ttf in src/main/resources/*linux*/Plugins/Core. But the current
	# implementation cannot handle multiple dirs .../resources/main,
	# .../resources/linux for one plugin.)
	remove(path('${core_plugin_in_freeze_dir}/Roboto Bold.ttf'))
	copy_python_library('send2trash', path('${core_plugin_in_freeze_dir}'))

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