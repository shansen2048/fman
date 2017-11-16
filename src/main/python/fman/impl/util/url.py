from fman.url import dirname, splitscheme
from pathlib import PurePosixPath

import re

def get_existing_pardir(url, is_dir):
	# N.B.: If `url` is a directory, it is returned, even though it is not a
	# strict parent directory.
	for candidate in _iter_parents(url):
		if is_dir(candidate):
			return candidate

def is_pardir(pardir, subdir):
	# N.B.: Every directory is a "pardir" of itself.
	for dir_ in _iter_parents(subdir):
		if dir_ == pardir:
			return True
	return False

def resolve(url):
	scheme, path = splitscheme(url)
	# Resolve a/./b and a//b:
	path = str(PurePosixPath(path))
	if path == '.':
		path = ''
	# Resolve a/../b
	path = re.subn(r'(^|/)([^/]+)/\.\.(?:$|/)', r'\1', path)[0]
	return scheme + path

def _iter_parents(url):
	prev_url = None
	while url != prev_url:
		yield url
		prev_url = url
		url = dirname(url)