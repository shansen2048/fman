from build_impl import path
from distutils.core import setup
from esky.bdist_esky import Executable
from os.path import join, relpath, normpath

import os

def get_data_files(resources_dir):
	result = []
	for (dir_, _, files) in os.walk(resources_dir):
		result.append((
			normpath(relpath(dir_, resources_dir)),
			[normpath(join(dir_, file_)) for file_ in files]
		))
	return result

setup(
	name='fman',
	data_files=get_data_files(path('target/resources')),
	version='0.0.1',
	options={
		'bdist_esky': {
			"freezer_module": "cxfreeze",
			'includes': ['PyQt5.QtCore', 'PyQt5.QtWidgets', 'PyQt5.QtGui'],
			# Esky's default implementation of appdir_from_executable(...)
			# treats OS X bundles specially and actually breaks them. Prevent
			# this special treatment:
			'bootstrap_code': 'appdir_from_executable = dirname\nbootstrap()',
			'dist_dir': path('target')
		}
	},
	scripts=[Executable(
		path('src/main/python/fman/main.py'), name='fman', gui_only=True
	)]
)