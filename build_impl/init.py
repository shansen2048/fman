from build_impl import is_windows, replace_in_file, replace_in_files, is_mac
from fbs.conf import path, OPTIONS
from io import BytesIO
from os import listdir
from os.path import join, dirname
from subprocess import run
from tempfile import TemporaryDirectory
from time import time
from urllib.request import urlopen
from zipfile import ZipFile

import sys

_QT_INSTALL_DIR = path('cache/Qt-5.6.2')

_SIP_DOWNLOAD_URL = \
	'https://downloads.sourceforge.net/project/pyqt/sip/sip-4.18.1/' \
	'sip-4.18.1.zip?r=https%3A%2F%2Fsourceforge.net%2Fprojects%2Fpyqt%2Ffiles' \
	'%2Fsip%2Fsip-4.18.1%2F&ts={time:.0f}&use_mirror=netix'.format(time=time())

_PYQT_DOWNLOAD_URL = \
	'https://downloads.sourceforge.net/project/pyqt/PyQt5/PyQt-5.6/' \
	'PyQt5_gpl-5.6.zip?r=https%3A%2F%2Fsourceforge.net%2Fprojects%2Fpyqt%2F' \
	'files%2FPyQt5%2FPyQt-5.6%2F&ts={time:.0f}&use_mirror=vorboss'\
	.format(time=time())

def install_sip():
	data = _download_file(_SIP_DOWNLOAD_URL)
	z = ZipFile(BytesIO(data))
	with TemporaryDirectory() as tmp_dir:
		z.extractall(tmp_dir)
		sip_dir = join(tmp_dir, listdir(tmp_dir)[0])
		_run_in_venv('python configure.py' + _EXTRA_FLAGS, cwd=sip_dir)
		if is_windows():
			siplib_makefile = join(sip_dir, 'siplib', 'Makefile')
			python35lib_absolute = _find_python_library('python35.lib')
			replace_in_file(
				siplib_makefile, ' python35.lib', ' ' + python35lib_absolute
			)
			makefile = join(sip_dir, 'Makefile')
			sipconfig_absolute = join(sip_dir, 'sipconfig.py')
			replace_in_file(
				makefile, 'copy /y sipconfig.py', 'copy /y ' + sipconfig_absolute
			)
		_run_make(cwd=sip_dir)
		_run_make('install', cwd=sip_dir)

if is_mac():
	_EXTRA_FLAGS = \
		' LFLAGS="-mmacosx-version-min=10.9" ' \
		'CFLAGS="-mmacosx-version-min=10.9" ' \
		'CXXFLAGS="-mmacosx-version-min=10.9"'
else:
	_EXTRA_FLAGS = ''

def install_pyqt():
	data = _download_file(_PYQT_DOWNLOAD_URL)
	z = ZipFile(BytesIO(data))
	with TemporaryDirectory() as tmp_dir:
		z.extractall(tmp_dir)
		pyqt_dir = join(tmp_dir, listdir(tmp_dir)[0])
		executable_suffix = '.exe' if is_windows() else ''
		qmake_path = join(_QT_INSTALL_DIR, 'bin', 'qmake' + executable_suffix)
		if is_windows():
			sip_exe_path = join(OPTIONS['venv_dir'], 'sip.exe')
		else:
			sip_exe_path = join(OPTIONS['venv_dir'], 'bin', 'sip')
		_run_in_venv(
			"python configure.py --confirm-license --qmake %s --sip %s%s"
			% (qmake_path, sip_exe_path, _EXTRA_FLAGS), cwd=pyqt_dir
		)
		if is_windows():
			python35lib_absolute = _find_python_library('python35.lib')
			replace_in_files(pyqt_dir, 'python35.lib', python35lib_absolute)
		result = _run_make(cwd=pyqt_dir)
		if result.returncode:
			# Try again:
			_run_make(cwd=pyqt_dir)
		_run_make('install', cwd=pyqt_dir)

def install_requirements(requirements_file):
	_run_in_venv("pip install -r " + requirements_file)

def _download_file(url):
	response = urlopen(url)
	data = response.read()
	assert response.code == 200, response.code
	return data

def _run_in_venv(command, **kwargs):
	if is_windows():
		activate_venv = \
			'call ' + join(OPTIONS['venv_dir'], 'Scripts', 'activate.bat')
	else:
		activate_venv = '. ' + join(OPTIONS['venv_dir'], 'bin', 'activate')
	run("%s && %s" % (activate_venv, command), shell=True, check=True, **kwargs)

def _run_make(*args, **kwargs):
	make = 'jom' if is_windows() else 'make'
	return run(' '.join([make] + list(args)), shell=True, check=True, **kwargs)

def _find_python_library(library_name):
	if not is_windows():
		raise NotImplementedError()
	return join(dirname(sys.executable), 'libs', library_name)