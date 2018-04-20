from fbs_runtime.system import is_windows
from fman.impl.util.path import parent
from pathlib import PurePath, PurePosixPath

import posixpath
import re
import string

def splitscheme(url):
	separator = '://'
	try:
		split_point = url.index(separator) + len(separator)
	except ValueError:
		raise ValueError('Not a valid URL: %r' % url) from None
	return url[:split_point], url[split_point:]

def as_url(local_file_path, scheme='file://'):
	# We purposely don't use Path#as_uri here because it escapes the URL.
	# For instance: Path('/a b').as_uri() returns 'file:///a%20b'. The entire
	# code base would get unnecessarily complicated if it had to escape URL
	# characters like %20 all the time. So we do not escape URLs and return
	# "file:///a b" instead:
	result = scheme + PurePath(local_file_path).as_posix()
	# On Windows, PurePath(\\server\folder).as_posix() ends with a slash.
	# Get rid of it:
	return re.sub(r'([^/])/$', r'\1', result)

def as_human_readable(url):
	scheme, path = splitscheme(url)
	if scheme != 'file://':
		return url
	if not is_windows():
		return path
	if re.fullmatch('[A-Z]:', path):
		return path + '\\'
	return _nturl2path_url2pathname(path)

def _nturl2path_url2pathname(url):
	"""
	Copied and modified from Python 3.5's nturl2path.url2pathname(...).
	"""
	# Windows itself uses ":" even in URLs.
	url = url.replace(':', '|')
	if not '|' in url:
		# No drive specifier, just convert slashes
		if url[:4] == '////':
			# path is something like ////host/path/on/remote/host
			# convert this to \\host\path\on\remote\host
			# (notice halving of slashes at the start of the path)
			url = url[2:]
		components = url.split('/')
		# make sure not to convert quoted slashes :-)
		return '\\'.join(components)
	comp = url.split('|')
	if len(comp) != 2 or comp[0][-1] not in string.ascii_letters:
		raise ValueError('Bad URL: ' + url)
	drive = comp[0][-1].upper()
	components = comp[1].split('/')
	path = drive + ':'
	for comp in components:
		if comp:
			path = path + '\\' + comp
	# Issue #11474 - handing url such as |c/|
	if path.endswith(':') and url.endswith('/'):
		path += '\\'
	return path

def dirname(url):
	scheme, path = splitscheme(url)
	return scheme + parent(path)

def basename(url):
	path = splitscheme(url)[1]
	return PurePosixPath(path).name

def join(url, *paths):
	scheme, path = splitscheme(url)
	result_path = PurePosixPath(path, *paths).as_posix()
	if result_path == '.':
		# This for instance happens when all paths were equal to ''
		result_path = ''
	return scheme + result_path

def relpath(target, base):
	target_scheme, target_path = splitscheme(target)
	base_scheme, base_path = splitscheme(base)
	if base_scheme != target_scheme:
		raise ValueError(
			"Cannot construct a relative path across different URL schemes "
			"(%s -> %s)" % (base_scheme, target_scheme)
		)
	return posixpath.relpath(target_path, start=base_path)