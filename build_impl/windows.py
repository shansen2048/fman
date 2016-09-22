from build_impl import run, path, generate_resources, OPTIONS, \
	copy_with_filtering, copy_python_library
from ctypes import windll
from os import rename, makedirs
from os.path import join, relpath, splitext
from shutil import copy
from subprocess import call, DEVNULL
from zipfile import ZipFile, ZIP_DEFLATED
from win32api import GetModuleFileName

import os

def exe():
	_run_pyinstaller()
	_add_missing_dlls()
	core_plugin_dir = path('target/fman/Plugins/Core')
	for library in ('send2trash', 'win32clipboard'):
		copy_python_library(library, core_plugin_dir)
	# win32clipboard requires another file:
	copy(GetModuleFileName(windll.pywintypes34._handle), core_plugin_dir)
	_move_pyinstaller_output_to_version_subdir()
	_build_launcher(dest=path('target/fman/fman.exe'))
	_generate_uninstaller()

def _run_pyinstaller():
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

def _add_missing_dlls():
	for dll in (
		'msvcr100.dll', 'msvcr110.dll', 'msvcp110.dll', 'vcruntime140.dll',
		'msvcp140.dll'
	):
		copy(join(r'c:\Windows\System32', dll), path('target/fman'))

def _move_pyinstaller_output_to_version_subdir():
	rename(path('target/fman'), path('target/pyinstaller'))
	versions_dir = path('target/fman/Versions')
	makedirs(versions_dir, exist_ok=True)
	rename(path('target/pyinstaller'), join(versions_dir, OPTIONS['version']))

def _build_launcher(dest):
	run([
		'go', 'build', '-o', dest, '-ldflags', '-H windowsgui',
		path('src/main/go/src/launcher/launcher.go')
	])

def sign_exe():
	for subdir, _, files in os.walk(path('target/fman')):
		for file_ in files:
			extension = splitext(file_)[1]
			if extension in ('.exe', '.cab', '.dll', '.ocx', '.msi', '.xpi'):
				file_path = join(subdir, file_)
				if not _is_signed(file_path):
					_sign(file_path)

def _generate_uninstaller():
	uninstaller_nsi = path('src/main/Uninstaller.nsi')
	copy_with_filtering(
		uninstaller_nsi, path('target'), {'version': OPTIONS['version']},
		files_to_filter=[uninstaller_nsi]
	)
	run(['makensis', path('target/Uninstaller.nsi')])
	run([
		path('target/UninstallerSetup.exe'), '/S', '/D=' + path('target/fman')
	])

def installer():
	installer_go = path('src/main/go/src/installer/installer.go')
	copy_with_filtering(
		installer_go, path('target/go/src/installer'),
		{'version': OPTIONS['version']}, files_to_filter=[installer_go]
	)
	# We need to replace \ by / for go-bindata:
	prefix = path('target/fman').replace('\\', '/')
	data_go = path('target/go/src/installer/data/data.go')
	run([
		'go-bindata', '-prefix', prefix, '-o', data_go,
		prefix + '/...'
	])
	_repl_in_file(data_go, b'package main', b'package data')
	setup = path('target/fmanSetup.exe')
	run(
		[
			'go', 'build', '-o', setup, '-ldflags', '-H windowsgui',
			path('target/go/src/installer/installer.go')
		],
		extra_env={
			'GOPATH': path('target/go') + ';' + os.environ['GOPATH']
		}
	)

def _repl_in_file(file_path, bytes_, replacement):
	if len(bytes_) != len(replacement):
		raise ValueError('Can only replace if len(bytes_) == len(replacement)')
	m = StateMachine(bytes_)
	with open(file_path, 'r+b') as f:
		while True:
			next_ = f.read(1)
			if not next_:
				raise ValueError('%r not found in %r.' % (bytes_, file_path))
			if m.feed(next_[0]):
				f.seek(-len(bytes_) + 1, 1)
				f.write(replacement)
				break

class StateMachine:
	def __init__(self, bytes_):
		self.bytes = bytes_
		self.i = 0
	def feed(self, byte_):
		try:
			is_eq = self.bytes[self.i] == byte_
		except IndexError:
			is_eq = False
		if is_eq:
			self.i += 1
		else:
			self.i = 0
		return self.i == len(self.bytes) - 1

def add_installer_manifest():
	"""
	If an .exe name contains "installer", "setup" etc., then at least Windows 10
	automatically opens a UAC prompt upon opening it. This can be avoided by
	adding a compatibility manifest to the .exe.
	"""
	run([
		'mt.exe', '-manifest', path('src/main/fmanSetup.exe.manifest'),
		'-outputresource:%s;1' % path('target/fmanSetup.exe')
	])

def sign_installer():
	_sign(path('target/fmanSetup.exe'), 'fman Setup', 'https://fman.io')

def _is_signed(file_path):
	return not call(
		['signtool', 'verify', '/pa', file_path], stdout=DEVNULL, stderr=DEVNULL
	)

def _sign(file_path, description='', url=''):
	args = [
		'signtool', 'sign', '/f', path('conf/windows/michaelherrmann.pfx'),
		'/p', 'Tu4suttmdpn!', '/tr', 'http://tsa.startssl.com/rfc3161'
	]
	if description:
		args.extend(['/d', description])
	if url:
		args.extend(['/du', url])
	args.append(file_path)
	run(args)
	args_sha256 = \
		args[:-1] + ['/as', '/fd', 'sha256', '/td', 'sha256'] + args[-1:]
	run(args_sha256)

def zip():
	with ZipFile(path('target/fman.zip'), 'w', ZIP_DEFLATED) as zip:
		for subdir, dirnames, filenames in os.walk(path('target/fman')):
			for filename in filenames:
				filepath = join(subdir, filename)
				arcname = relpath(filepath, path('target'))
				zip.write(filepath, arcname)