from build_impl import run, path, generate_resources
from os.path import join
from shutil import copy

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