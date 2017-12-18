from fbs.conf import path, OPTIONS

import os
import subprocess
import sys

def run():
	env = dict(os.environ)
	pythonpath = path('src/main/python')
	old_pythonpath = env.get('PYTHONPATH', '')
	if old_pythonpath:
		pythonpath += os.pathsep + old_pythonpath
	env['PYTHONPATH'] = pythonpath
	subprocess.run([sys.executable, OPTIONS['main_module']], env=env)
