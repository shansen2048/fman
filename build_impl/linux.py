from build_impl import path, generate_resources, OPTIONS
from distutils.core import setup
from esky.bdist_esky import Executable
from os.path import join, relpath, normpath, basename, splitext
from zipfile import ZipFile, ZIP_DEFLATED

import os
import sys

def esky():
	generate_resources()
	_run_esky()
	with ZipFile(_get_esky_zip_path(), 'a', ZIP_DEFLATED) as zip:
		zip.write(r'c:\Windows\System32\msvcr100.dll', r'msvcr100.dll')

def _get_esky_zip_path():
	return path('target/fman-%s.win-amd64.zip' % OPTIONS['version'])

def _get_esky_subdir():
	return splitext(basename(_get_esky_zip_path()))[0]

def _run_esky():
	sys.path.append(path('src/main/python'))
	try:
		setup(
			script_name=basename(__file__),
			script_args=['bdist_esky'],
			name='fman',
			data_files=_get_data_files(path('target/resources')),
			version=OPTIONS['version'],
			options={
				'bdist_esky': {
					"freezer_module": "cxfreeze",
					'includes': [
						'PyQt5.QtCore', 'PyQt5.QtWidgets', 'PyQt5.QtGui',
						# Transitive dependencies:
						'PyQt5.QtDBus', 'PyQt5.QtPrintSupport'
					],
					'dist_dir': path('target')
				}
			},
			scripts=[Executable(
				path('src/main/python/fman/main.py'), name='fman', gui_only=True
			)]
		)
	finally:
		sys.path.pop()

def _get_data_files(resources_dir):
	result = []
	for (dir_, _, files) in os.walk(resources_dir):
		result.append((
			normpath(relpath(dir_, resources_dir)),
			[normpath(join(dir_, file_)) for file_ in files]
		))
	return result

def exe():
	with ZipFile(_get_esky_zip_path(), 'r') as f:
		f.extractall(path('target/fman'))