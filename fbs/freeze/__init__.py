from fbs import path, SETTINGS
from os import rename
from subprocess import run

def run_pyinstaller(extra_args=None):
	if extra_args is None:
		extra_args = []
	app_name = SETTINGS['app_name']
	cmdline = [
		'pyinstaller',
		'--name', app_name,
		'--noupx'
	] + extra_args + [
		'--distpath', path('target'),
		'--specpath', path('target/build'),
		'--workpath', path('target/build'),
		SETTINGS['main_module']
	]
	run(cmdline, check=True)
	pyinstaller_output_dir = path('target/' + app_name)
	rename(pyinstaller_output_dir, path('target/app'))