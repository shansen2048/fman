from argparse import ArgumentParser
from fbs import conf
from fbs.conf import path, SETTINGS, load_settings
from os import listdir, remove, unlink
from os.path import join, isfile, isdir, islink, abspath
from shutil import rmtree
from unittest import TestSuite, TextTestRunner, defaultTestLoader

import os
import subprocess
import sys

def main(project_dir):
	init(abspath(project_dir))
	args = _parse_cmdline()
	result = _COMMANDS[args.cmd](*args.args)
	if result:
		print(result)

def init(project_dir):
	SETTINGS['project_dir'] = project_dir
	SETTINGS.update(load_settings(join(project_dir, 'build.json')))

def command(f):
	_COMMANDS[f.__name__] = f
	return f

_COMMANDS = {}

@command
def run():
	env = dict(os.environ)
	pythonpath = path('src/main/python')
	old_pythonpath = env.get('PYTHONPATH', '')
	if old_pythonpath:
		pythonpath += os.pathsep + old_pythonpath
	env['PYTHONPATH'] = pythonpath
	subprocess.run([sys.executable, SETTINGS['main_module']], env=env)

@command
def test():
	sys.path.append(path('src/main/python'))
	suite = TestSuite()
	for test_dir in map(path, SETTINGS['test_dirs']):
		sys.path.append(test_dir)
		try:
			dir_names = listdir(test_dir)
		except FileNotFoundError:
			continue
		for dir_name in dir_names:
			dir_path = join(test_dir, dir_name)
			if isfile(join(dir_path, '__init__.py')):
				suite.addTest(defaultTestLoader.discover(
					dir_name, top_level_dir=test_dir
				))
	TextTestRunner().run(suite)

@command
def clean():
	try:
		rmtree(path('target'))
	except FileNotFoundError:
		return
	except OSError:
		# In a docker container, target/ may be mounted so we can't delete it.
		# Delete its contents instead:
		for f in listdir(path('target')):
			fpath = join(path('target'), f)
			if isdir(fpath):
				rmtree(fpath, ignore_errors=True)
			elif isfile(fpath):
				remove(fpath)
			elif islink(fpath):
				unlink(fpath)

def _parse_cmdline():
	parser = ArgumentParser(description='fbs')
	parser.add_argument('cmd')
	parser.add_argument('args', metavar='arg', nargs='*')
	return parser.parse_args()