from build_impl import run, path, generate_resources, get_option
from os.path import join, relpath
from shutil import copy
from zipfile import ZipFile, ZIP_DEFLATED

import os

def esky():
	generate_resources()
	run(
		['python', path('setup.py'), 'bdist_esky'],
		extra_env={'PYTHONPATH': path('src/main/python')}
	)
	esky_name = 'fman-%s.win-amd64' % get_option('version')
	with ZipFile(path('target/%s.zip' % esky_name), 'a', ZIP_DEFLATED) as zip:
		zip.write(r'c:\Windows\System32\msvcr100.dll', r'msvcr100.dll')
		for dll in ('msvcr100.dll', 'msvcr110.dll', 'msvcp110.dll'):
			zip.write(join(r'c:\Windows\System32', dll), join(esky_name, dll))

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

def setup():
	run(['makensis', path('src/main/Setup.nsi')])

def zip():
	with ZipFile(path('target/fman.zip'), 'w', ZIP_DEFLATED) as zip:
		for subdir, dirnames, filenames in os.walk(path('target/fman')):
			for filename in filenames:
				filepath = join(subdir, filename)
				arcname = relpath(filepath, path('target'))
				zip.write(filepath, arcname)