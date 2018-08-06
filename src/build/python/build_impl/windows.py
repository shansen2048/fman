from build_impl import copy_python_library, upload_to_s3
from fbs import path, SETTINGS
from fbs.cmdline import command
from fbs.freeze.windows import freeze_windows
from fbs.resources import copy_with_filtering
from datetime import date
from os import rename, makedirs
from os.path import join, splitext, dirname, basename
from shutil import copy, rmtree
from subprocess import call, DEVNULL, run

import hashlib
import json
import os

@command
def init():
	_install_go_dependencies()

def _install_go_dependencies():
	env = dict(os.environ)
	env['GOPATH'] = path('src/main/go')
	go_get = lambda dep: run(['go', 'get', dep], env=env, check=True)
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
	freeze_windows(extra_pyinstaller_args=[
		# Required by send2trash, which is used in the Core plugin:
		'--hidden-import', 'ctypes.wintypes',
		# Required by the Core plugin:
		'--hidden-import', 'adodbapi',
		'--hidden-import', 'win32com.shell.shell',
		'--hidden-import', 'win32com.shell.shellcon',
		'--hidden-import', 'win32gui',
		'--hidden-import', 'winpty'
	])
	_copy_winpty_files()
	rmtree(path('${freeze_dir}/Plugins/Core/bin/mac'))
	rmtree(path('${freeze_dir}/Plugins/Core/bin/linux'))
	copy_python_library('send2trash', path('${freeze_dir}/Plugins/Core'))
	_move_pyinstaller_output_to_version_subdir()
	_build_launcher(dest=path('${freeze_dir}/fman.exe'))
	_generate_uninstaller()

def _copy_winpty_files():
	import winpty
	winpty_dir = dirname(winpty.__file__)
	copy(join(winpty_dir, 'winpty-agent.exe'), path('${freeze_dir}'))

def _move_pyinstaller_output_to_version_subdir():
	rename(path('${freeze_dir}'), path('${freeze_dir}.tmp'))
	versions_dir = path('${freeze_dir}/Versions')
	makedirs(versions_dir, exist_ok=True)
	rename(path('${freeze_dir}.tmp'), join(versions_dir, SETTINGS['version']))

def _build_launcher(dest):
	major_str, minor_str, patch_str = SETTINGS['version'].split('.')
	if patch_str.endswith('-SNAPSHOT'):
		patch_str = patch_str[:-len('-SNAPSHOT')]
	copy_with_filtering(
		path('src/main/go/src/launcher'), path('target/go/src/launcher'), {
			'version': SETTINGS['version'],
			'version.major': major_str,
			'version.minor': minor_str,
			'version.patch': patch_str,
			'year': date.today().year
		}, files_to_filter=[path("src/main/go/src/launcher/versioninfo.json")]
	)
	copy(path('src/main/icons/Icon.ico'), path('target/go/src/launcher'))
	_run_go('generate', 'launcher')
	_run_go('build', '-o', dest, '-ldflags', '-H windowsgui', 'launcher')

def _run_go(*args):
	env = dict(os.environ)
	env['GOPATH'] = path('target/go') + ';' + path('src/main/go')
	env['PATH'] = path('src/main/go/bin') + ';' + os.environ['PATH']
	run(['go'] + list(args), env=env, check=True)

@command
def sign_exe():
	for subdir, _, files in os.walk(path('${freeze_dir}')):
		for file_ in files:
			extension = splitext(file_)[1]
			if extension in ('.exe', '.cab', '.dll', '.ocx', '.msi', '.xpi'):
				file_path = join(subdir, file_)
				if not _is_signed(file_path):
					_sign(file_path)

def _generate_uninstaller():
	uninstaller_nsi = path('src/main/Uninstaller.nsi')
	copy_with_filtering(
		uninstaller_nsi, path('target'), {'version': SETTINGS['version']},
		files_to_filter=[uninstaller_nsi]
	)
	run(['makensis', path('target/Uninstaller.nsi')], check=True)
	run([
		path('target/UninstallerSetup.exe'), '/S', '/D=' + path('${freeze_dir}')
	], check=True)

@command
def installer():
	installer_go = path('src/main/go/src/installer/installer.go')
	copy_with_filtering(
		installer_go, path('target/go/src/installer'),
		{'version': SETTINGS['version']}, files_to_filter=[installer_go]
	)
	# We need to replace \ by / for go-bindata:
	prefix = path('${freeze_dir}').replace('\\', '/')
	data_go = path('target/go/src/installer/data/data.go')
	run([
		path('src/main/go/bin/go-bindata'), '-prefix', prefix, '-o', data_go,
		prefix + '/...'
	], check=True)
	_repl_in_file(data_go, b'package main', b'package data')
	setup = path('target/fmanSetup.exe')
	args = ['build', '-o', setup]
	if SETTINGS['release']:
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
	], check=True)

@command
def sign_installer():
	_sign(path('target/fmanSetup.exe'), 'fman Setup', 'https://fman.io')

def _is_signed(file_path):
	return SignHelper.instance().is_signed(file_path)

def _sign(file_path, description='', url=''):
	SignHelper.instance().sign(file_path, description, url)

class SignHelper:
	_INSTANCE = None
	@classmethod
	def instance(cls):
		if cls._INSTANCE is None:
			cls._INSTANCE = cls(path('cache/signed'))
		return cls._INSTANCE
	def __init__(self, cache_dir):
		self._cache_dir = cache_dir
	def is_signed(self, file_path):
		return not call(
			['signtool', 'verify', '/pa', file_path], stdout=DEVNULL,
			stderr=DEVNULL
		)
	def sign(self, file_path, description, url):
		json_path = self._get_json_path(file_path)
		try:
			with open(json_path) as f:
				cached = json.load(f)
			is_in_cache = description == cached['description'] and \
			              url == cached['url'] and \
			              self._hash(file_path) == cached['hash']
		except FileNotFoundError:
			is_in_cache = False
		if not is_in_cache:
			self._sign(file_path, description, url)
		copy(self._get_path_in_cache(file_path), file_path)
	def _sign(self, file_path, description, url):
		path_in_cache = self._get_path_in_cache(file_path)
		makedirs(dirname(path_in_cache), exist_ok=True)
		copy(file_path, path_in_cache)
		hash_ = self._hash(path_in_cache)
		self._run_signtool(path_in_cache)
		with open(self._get_json_path(file_path), 'w') as f:
			json.dump({
				'description': description,
				'url': url,
				'hash': hash_
			}, f)
	def _get_json_path(self, file_path):
		return self._get_path_in_cache(file_path) + '.json'
	def _get_path_in_cache(self, file_path):
		return join(self._cache_dir, basename(file_path))
	def _run_signtool(self, file_path, description='', url=''):
		args = [
			'signtool', 'sign', '/f', path('conf/windows/michaelherrmann.pfx'),
			'/p', 'Tu4suttmdpn', '/tr', 'http://sha256timestamp.ws.symantec.com/sha256/timestamp'
		]
		if description:
			args.extend(['/d', description])
		if url:
			args.extend(['/du', url])
		args.append(file_path)
		run(args, check=True)
		args_sha256 = \
			args[:-1] + ['/as', '/fd', 'sha256', '/td', 'sha256'] + args[-1:]
		run(args_sha256, check=True)
	def _hash(self, file_path):
		bufsize = 65536
		hasher = hashlib.md5()
		with open(file_path, 'rb') as f:
			buf = f.read(bufsize)
			while buf:
				hasher.update(buf)
				buf = f.read(bufsize)
		return hasher.hexdigest()

@command
def upload():
	if SETTINGS['release']:
		src_path = path('target/fmanSetup.exe')
		dest_path = SETTINGS['version'] + '/fmanSetup.exe'
		upload_to_s3(src_path, dest_path)
		print('\nDone. Please upload fmanSetup.exe to update.fman.io now.')