"""
Install all Python dependencies. Assumes Qt has already been compiled.
Run with Python 3.5 from the command prompt from which Qt can be built.
"""

from io import BytesIO
from os import listdir
from os.path import abspath, join, dirname, splitext, expanduser, exists
from subprocess import run
from tempfile import TemporaryDirectory
from time import time
from urllib.request import urlopen
from venv import EnvBuilder
from zipfile import ZipFile

import os
import sys

_FMAN_SRC_DIR = expanduser(join(*'~/dev/fman'.split('/')))
_PYTHON_HOME = dirname(sys.executable)
_QT_INSTALL_DIR = join(_FMAN_SRC_DIR, 'lib', 'windows', 'Qt-5.6.2')
_VENV_INSTALL_DIR = join(_FMAN_SRC_DIR, 'venv')
_VENV_ACTIVATE = join(_VENV_INSTALL_DIR, 'Scripts', 'activate.bat')

def _create_venv():
  if exists(_VENV_INSTALL_DIR):
    raise ValueError('%s already exists' % _VENV_INSTALL_DIR)
  builder = EnvBuilder(with_pip=True)
  builder.create(_VENV_INSTALL_DIR)

def _replace_in_file(path, string, replacement, check_found=True):
  with open(path, 'r') as f:
    contents = f.read()
  if check_found:
    assert string in contents, contents
  with open(path, 'w') as f:
    f.write(contents.replace(string, replacement))

def replace_in_files(dir_, string, replacement):
    for subdir, _, files in os.walk(dir_):
        for file_ in files:
            ext = splitext(file_)[1]
            if ext in ('.exe', '.lib', '.dll', '.pyc', '.dmp', '.cer', '.pfx', '.idb', '.dblite', '.avi', '.bmp', '.msi', '.ico', '.pdb', '.res', '.rc'):
                continue
            f_path = join(subdir, file_)
            try:
              _replace_in_file(f_path, string, replacement, check_found=False)
            except UnicodeDecodeError:
              pass

def _install_sip():
  sip_url = 'https://downloads.sourceforge.net/project/pyqt/sip/sip-4.18.1/sip-4.18.1.zip?r=https%3A%2F%2Fsourceforge.net%2Fprojects%2Fpyqt%2Ffiles%2Fsip%2Fsip-4.18.1%2F&ts={time:.0f}&use_mirror=netix'.format(time=time())
  response = urlopen(sip_url)
  data = response.read()
  assert response.code == 200, response.code
  z = ZipFile(BytesIO(data))
  with TemporaryDirectory() as tmp_dir:
    z.extractall(tmp_dir)
    sip_dir = join(tmp_dir, listdir(tmp_dir)[0])
    run("call %s && python configure.py" % (_VENV_ACTIVATE,), shell=True, check=True, cwd=sip_dir)
    siplib_makefile = join(sip_dir, 'siplib', 'Makefile')
    python35lib_absolute = join(_PYTHON_HOME, 'libs', 'python35.lib')
    _replace_in_file(siplib_makefile, ' python35.lib', ' ' + python35lib_absolute)
    makefile = join(sip_dir, 'Makefile')
    sipconfig_absolute = join(sip_dir, 'sipconfig.py')
    _replace_in_file(makefile, 'copy /y sipconfig.py', 'copy /y ' + sipconfig_absolute)
    run("jom", shell=True, check=True, cwd=sip_dir)
    run("jom install", shell=True, check=True, cwd=sip_dir)

def _install_pyqt():
  pyqt_url = 'https://downloads.sourceforge.net/project/pyqt/PyQt5/PyQt-5.6/PyQt5_gpl-5.6.zip?r=https%3A%2F%2Fsourceforge.net%2Fprojects%2Fpyqt%2Ffiles%2FPyQt5%2FPyQt-5.6%2F&ts={time:.0f}&use_mirror=vorboss'.format(time=time())
  response = urlopen(pyqt_url)
  data = response.read()
  assert response.code == 200, response.code
  z = ZipFile(BytesIO(data))
  with TemporaryDirectory() as tmp_dir:
    z.extractall(tmp_dir)
    pyqt_dir = join(tmp_dir, listdir(tmp_dir)[0])
    qmake_path = join(_QT_INSTALL_DIR, 'bin', 'qmake.exe')
    sip_exe_path = join(_VENV_INSTALL_DIR, 'sip.exe')
    run("call %s && python configure.py --confirm-license --qmake %s --sip %s" % (_VENV_ACTIVATE, qmake_path, sip_exe_path), shell=True, check=True, cwd=pyqt_dir)
    python35lib_absolute = join(_PYTHON_HOME, 'libs', 'python35.lib')
    replace_in_files(pyqt_dir, 'python35.lib', python35lib_absolute)
    result = run("jom", shell=True, cwd=pyqt_dir)
    if result.returncode:
      # Try again:
      run("jom", shell=True, check=True, cwd=pyqt_dir)
    run("jom install", shell=True, check=True, cwd=pyqt_dir)

def _install_requirements():
  requirements_file = join(_FMAN_SRC_DIR, 'requirements', 'windows.txt')
  run(r"call %s && pip install -r %s" % (_VENV_ACTIVATE, requirements_file), shell=True, check=True)

if __name__ == '__main__':
  _create_venv()
  _install_sip()
  _install_pyqt()
  _install_requirements()