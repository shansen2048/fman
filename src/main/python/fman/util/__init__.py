from getpass import getuser
from os import listdir
from os.path import join, basename, expanduser

def listdir_absolute(dir_path):
	return [join(dir_path, file_name) for file_name in listdir(dir_path)]

def get_user():
	try:
		return getuser()
	except:
		return basename(expanduser('~'))