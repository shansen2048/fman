from fbs.conf import OPTIONS
from fbs.platform import is_windows
from os.path import join
from subprocess import run
from venv import EnvBuilder

def create_venv(venv_dir=None, system_site_packages=False):
	if venv_dir is None:
		venv_dir = OPTIONS['venv_dir']
	builder = \
		EnvBuilder(with_pip=True, system_site_packages=system_site_packages)
	builder.create(venv_dir)

def install_requirements(requirements_file):
	run_in_venv("pip install -r " + requirements_file)

def run_in_venv(command, cwd=None):
	if is_windows():
		activate_venv = \
			'call ' + join(OPTIONS['venv_dir'], 'Scripts', 'activate.bat')
	else:
		activate_venv = '. ' + join(OPTIONS['venv_dir'], 'bin', 'activate')
	run("%s && %s" % (activate_venv, command), shell=True, check=True, cwd=cwd)