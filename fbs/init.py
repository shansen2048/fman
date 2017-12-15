from fbs.conf import OPTIONS
from venv import EnvBuilder

def create_venv(venv_dir=None, system_site_packages=False):
	if venv_dir is None:
		venv_dir = OPTIONS['venv_dir']
	builder = \
		EnvBuilder(with_pip=True, system_site_packages=system_site_packages)
	builder.create(venv_dir)