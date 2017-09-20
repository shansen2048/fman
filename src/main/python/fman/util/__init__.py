from functools import lru_cache
from getpass import getuser
from os import listdir
from os.path import join, basename, expanduser, dirname, realpath, relpath, \
	pardir, splitdrive

import os

def listdir_absolute(dir_path):
	return [join(dir_path, file_name) for file_name in listdir(dir_path)]

def get_user():
	try:
		return getuser()
	except:
		return basename(expanduser('~'))

def is_below_dir(file_path, directory):
	if splitdrive(file_path)[0].lower() != splitdrive(directory)[0].lower():
		return False
	rel = relpath(realpath(dirname(file_path)), realpath(directory))
	return not (rel == pardir or rel.startswith(pardir + os.sep))

def parse_version(version_str):
	if version_str.endswith('-SNAPSHOT'):
		version_str = version_str[:-len('-SNAPSHOT')]
	return tuple(map(int, version_str.split('.')))

def cached_property(getter):
	return property(lru_cache()(getter))