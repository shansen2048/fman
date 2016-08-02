from build_impl import run, path, generate_resources, OPTIONS
from distutils.core import setup
from esky.bdist_esky import Executable
from os.path import join, relpath, normpath, basename
from shutil import copy
from zipfile import ZipFile, ZIP_DEFLATED

import os
import sys

def esky():
	generate_resources()
	_run_esky()
	esky_name = 'fman-%s.win-amd64' % OPTIONS['version']
	with ZipFile(path('target/%s.zip' % esky_name), 'a', ZIP_DEFLATED) as zip:
		zip.write(r'c:\Windows\System32\msvcr100.dll', r'msvcr100.dll')
		for dll in ('msvcr100.dll', 'msvcr110.dll', 'msvcp110.dll'):
			zip.write(join(r'c:\Windows\System32', dll), join(esky_name, dll))

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
	run([
		'pyinstaller',
		'--name', 'fman',
		'--windowed',
		'--distpath', path('target'),
		'--specpath', path('target/build'),
		'--workpath', path('target/build'),
		path('src/main/python/fman/main.py')
	])
	generate_resources(dest_dir=path('target/fman'))
	for dll in ('msvcr100.dll', 'msvcr110.dll', 'msvcp110.dll'):
		copy(join(r'c:\Windows\System32', dll), path('target/fman'))

def installer():
	run(['makensis', path('src/main/Setup.nsi')])

def zip():
	with ZipFile(path('target/fman.zip'), 'w', ZIP_DEFLATED) as zip:
		for subdir, dirnames, filenames in os.walk(path('target/fman')):
			for filename in filenames:
				filepath = join(subdir, filename)
				arcname = relpath(filepath, path('target'))
				zip.write(filepath, arcname)