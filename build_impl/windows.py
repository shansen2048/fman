from build_impl import run, path, generate_resources
from os.path import join, relpath
from shutil import copy
from zipfile import ZipFile, ZIP_DEFLATED

import os

def exe():
	run([
		'pyinstaller',
		'--name', 'fman',
		'--windowed', '--noupx',
		'--distpath', path('target'),
		'--specpath', path('target/build'),
		'--workpath', path('target/build'),
		path('src/main/python/fman/main.py')
	])
	generate_resources(dest_dir=path('target/fman'))
	for dll in ('msvcr100.dll', 'msvcr110.dll', 'msvcp110.dll'):
		copy(join(r'c:\Windows\System32', dll), path('target/fman'))

def sign_exe():
	_sign(path('target/fman/fman.exe'), 'fman')

def installer():
	run(['makensis', path('src/main/Setup.nsi')])

def sign_installer():
	_sign(path('target/fman Setup.exe'), 'fman Setup')

def _sign(file_path, description):
	run([
		'signtool', 'sign', '/f', path('conf/windows/michaelherrmann.pfx'),
		'/p', 'Tu4suttmdpn!', '/tr', 'http://tsa.startssl.com/rfc3161',
		'/d', description, '/du', 'https://fman.io', file_path
	])

def zip():
	with ZipFile(path('target/fman.zip'), 'w', ZIP_DEFLATED) as zip:
		for subdir, dirnames, filenames in os.walk(path('target/fman')):
			for filename in filenames:
				filepath = join(subdir, filename)
				arcname = relpath(filepath, path('target'))
				zip.write(filepath, arcname)