from getpass import getuser
from os import listdir
from os.path import join, basename, expanduser, dirname, realpath, relpath, \
	pardir

import os

def listdir_absolute(dir_path):
	return [join(dir_path, file_name) for file_name in listdir(dir_path)]

def get_user():
	try:
		return getuser()
	except:
		return basename(expanduser('~'))

def is_in_subdir(file_path, directory):
	rel = relpath(realpath(dirname(file_path)), realpath(directory))
	return not (rel == pardir or rel.startswith(pardir + os.sep))