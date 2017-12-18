from build_impl import run, generate_resources, OPTIONS, copy_with_filtering, \
	copy_python_library, run_pyinstaller, upload_to_s3
from fbs import command
from fbs.conf import path
from datetime import date
from os import rename, makedirs, remove
from os.path import join, splitext, dirname
from shutil import copy
from subprocess import call, DEVNULL

import os
import sys

@command
def init():
	_install_go_dependencies()

def _install_go_dependencies():
	gopath = {'GOPATH': path('src/main/go')}
	go_get = lambda dep: run(['go', 'get', dep], extra_env=gopath)
	# We used to have a solution with third-party tool `godep` here.
	# This let us tie down the specific versions of our dependencies.
	# However, the tool did not work with some of our dependencies.
	# So just use `go get` and live with the fact that we will now
	# get different versions every time this function is called.
	go_get('golang.org/x/sys/windows')
	go_get('github.com/josephspurrier/goversioninfo/cmd/goversioninfo')
	go_get('github.com/jteeuwen/go-bindata/...')

@command
def exe():
	run_pyinstaller(extra_args=[
		'--windowed', '--icon', path('src/main/resources/base/fman.ico'),
		# Required by send2trash, which is used in the Core plugin:
		'--hidden-import', 'ctypes.wintypes',
		# Required by the Core plugin:
		'--hidden-import', 'adodbapi'
	])
	# PyInstaller somehow corrupts python3*.dll - see:
	# https://github.com/pyinstaller/pyinstaller/issues/2526
	# Restore the uncorrupted original:
	for dll_name in ('python3.dll', 'python35.dll'):
		remove(path('target/fman/' + dll_name))
		copy(join(dirname(sys.executable), dll_name), path('target/fman'))
	generate_resources(dest_dir=path('target/fman'))
	_add_missing_dlls()
	copy_python_library('send2trash', path('target/fman/Plugins/Core'))
	copy_python_library('ordered_set', path('target/fman/Plugins/Core'))
	_move_pyinstaller_output_to_version_subdir()
	_build_launcher(dest=path('target/fman/fman.exe'))
	_generate_uninstaller()

def _add_missing_dlls():
	for dll in (
		'msvcr100.dll', 'msvcr110.dll', 'msvcp110.dll', 'vcruntime140.dll',
		'msvcp140.dll', 'concrt140.dll', 'vccorlib140.dll',
		'api-ms-win-crt-multibyte-l1-1-0.dll'
	):
		copy(join(r'c:\Windows\System32', dll), path('target/fman'))

def _move_pyinstaller_output_to_version_subdir():
	rename(path('target/fman'), path('target/pyinstaller'))
	versions_dir = path('target/fman/Versions')
	makedirs(versions_dir, exist_ok=True)
	rename(path('target/pyinstaller'), join(versions_dir, OPTIONS['version']))

def _build_launcher(dest):
	major_str, minor_str, patch_str = OPTIONS['version'].split('.')
	if patch_str.endswith('-SNAPSHOT'):
		patch_str = patch_str[:-len('-SNAPSHOT')]
	copy_with_filtering(
		path('src/main/go/src/launcher'), path('target/go/src/launcher'), {
			'version': OPTIONS['version'],
			'version.major': major_str,
			'version.minor': minor_str,
			'version.patch': patch_str,
			'year': date.today().year
		}, files_to_filter=[path("src/main/go/src/launcher/versioninfo.json")]
	)
	copy(
		path('src/main/resources/base/fman.ico'),
		path('target/go/src/launcher')
	)
	_run_go('generate', 'launcher')
	_run_go('build', '-o', dest, '-ldflags', '-H windowsgui', 'launcher')

def _run_go(*args):
	run(
		['go'] + list(args),
		extra_env={
			'GOPATH': path('target/go') + ';' + path('src/main/go'),
			'PATH': path('src/main/go/bin') + ';' + os.environ['PATH']
		}
	)

@command
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

@command
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
		path('src/main/go/bin/go-bindata'), '-prefix', prefix, '-o', data_go,
		prefix + '/...'
	])
	_repl_in_file(data_go, b'package main', b'package data')
	setup = path('target/fmanSetup.exe')
	args = ['build', '-o', setup]
	if OPTIONS['release']:
		# The flags below hide the console window. We only apply them during a
		# release so we can use fmt.Print* while developing.
		args.extend(['-ldflags', '-H windowsgui'])
	args.append(path('target/go/src/installer/installer.go'))
	_run_go(*args)

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

@command
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

@command
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

@command
def upload():
	if OPTIONS['release']:
		src_path = path('target/fmanSetup.exe')
		dest_path = OPTIONS['version'] + '/fmanSetup.exe'
		upload_to_s3(src_path, dest_path)
		print('\nDone. Please upload fmanSetup.exe to update.fman.io now.')