from os import listdir

from cx_Freeze import setup, Executable
from os.path import dirname, join, pardir

import sys

base = None
if sys.platform == 'win32':
	base = 'Win32GUI'

this_dir = dirname(__file__)
src_dir = join(this_dir, pardir, pardir)
resources_dir = join(src_dir, 'main', 'resources')

def listdir_absolute_paths(dir_):
	return [join(dir_, file_) for file_ in listdir(dir_)]

options = {
	'build_exe': {
		'include_files': listdir_absolute_paths(resources_dir),
		'packages': ['PyQt5.QtCore', 'PyQt5.QtWidgets', 'PyQt5.QtGui'],
		'silent': True
	},
	'bdist_mac': {
		'bundle_name': 'fman'
	},
	'bdist_dmg': {
		'volume_label': 'fman',
		'applications_shortcut': True
	}
}

executables = [Executable(
	join(this_dir, 'fman', 'main.py'), base=base, targetName='fman'
)]

setup(
	name='fman',
	version='0.0.1',
	options=options,
	executables=executables
)