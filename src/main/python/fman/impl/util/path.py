from fman.impl.util.system import is_windows
from os.path import splitdrive, normpath, expanduser, realpath
from pathlib import PurePosixPath

def make_absolute(file_path, cwd):
	if normpath(file_path) == '.':
		return cwd
	file_path = expanduser(file_path)
	file_path = add_backslash_to_drive_if_missing(file_path)
	return realpath(file_path)

def add_backslash_to_drive_if_missing(file_path): # Copied from Core plugin
	"""
	Normalize "C:" -> "C:\". Required for some path functions on Windows.
	"""
	if is_windows() and file_path:
		drive_or_unc, path = splitdrive(file_path)
		is_drive = drive_or_unc.endswith(':')
		if is_drive and file_path == drive_or_unc:
			return file_path + '\\'
	return file_path

def parent(path):
	if path == '/':
		return ''
	result = str(PurePosixPath(path).parent) if path else ''
	return '' if result == '.' else result