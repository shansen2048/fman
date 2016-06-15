from distutils.core import setup
from esky.bdist_esky import Executable
from fman.util import system
from os.path import dirname, join, pardir, relpath, normpath

import os

this_dir = dirname(__file__)
src_dir = join(this_dir, pardir, pardir)
proj_dir = join(src_dir, pardir)
target_dir = join(proj_dir, 'target')
resources_dir = join(src_dir, 'main', 'resources')

def get_resource_files(resources_subdir_name):
	result = []
	resources_subdir = join(resources_dir, resources_subdir_name)
	for (dir_, _, files) in os.walk(resources_subdir):
		result.append((
			normpath(relpath(dir_, resources_subdir)),
			[normpath(join(dir_, file_)) for file_ in files]
		))
	return result

data_files = get_resource_files('base')
if system.is_linux():
	data_files.extend(get_resource_files('linux'))
elif system.is_windows():
	data_files.extend(get_resource_files('windows'))

setup(
	name='fman',
	data_files=data_files,
	version='0.0.1',
	options={
		'bdist_esky': {
			"freezer_module": "cxfreeze",
			'includes': ['PyQt5.QtCore', 'PyQt5.QtWidgets', 'PyQt5.QtGui'],
			# Esky's default implementation of appdir_from_executable(...)
			# treats OS X bundles specially and actually breaks them. Prevent
			# this special treatment:
			'bootstrap_code': 'appdir_from_executable = dirname\nbootstrap()',
			'dist_dir': target_dir
		}
	},
	scripts=[Executable(
		join(this_dir, 'fman', 'main.py'), name='fman', gui_only=True
	)]
)