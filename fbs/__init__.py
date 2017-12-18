from argparse import ArgumentParser
from fbs.conf import path, OPTIONS, load_options
from os import listdir, remove, unlink
from os.path import join, isfile, isdir, islink, abspath
from shutil import rmtree
from unittest import TestSuite, TextTestRunner, defaultTestLoader

import os
import subprocess
import sys

def main(project_dir):
	OPTIONS['project_dir'] = abspath(project_dir)
	OPTIONS.update(load_options(join(project_dir, 'build.json')))
	parser = ArgumentParser(description='fbs')
	parser.add_argument('cmd')
	parser.add_argument('args', metavar='arg', nargs='*')
	args = parser.parse_args()
	result = _COMMANDS[args.cmd](*args.args)
	if result:
		print(result)

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
	subprocess.run([sys.executable, OPTIONS['main_module']], env=env)

@command
def test():
	sys.path.append(path('src/main/python'))
	suite = TestSuite()
	for test_dir in OPTIONS['test_dirs']:
		sys.path.append(test_dir)
		for dir_name in listdir(test_dir):
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