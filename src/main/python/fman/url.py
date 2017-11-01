from pathlib import PurePath, PurePosixPath
from urllib.parse import urlparse
from urllib.request import url2pathname

import os.path
import posixpath

def splitscheme(url):
	separator = '://'
	try:
		split_point = url.index(separator) + len(separator)
	except ValueError:
		raise ValueError('Not a valid URL: %r' % url) from None
	return url[:split_point], url[split_point:]

def as_file_url(file_path):
	# We purposely don't use Path#as_uri here because it escapes the URL.
	# For instance: Path('/a b').as_uri() returns 'file:///a%20b'. The entire
	# code base would get unnecessarily complicated if it had to escape URL
	# characters like %20 all the time. So we do not escape URLs and return
	# "file:///a b" instead:
	return 'file://' + PurePath(file_path).as_posix()

def as_human_readable(url):
	parsed = urlparse(url)
	if parsed.scheme != 'file':
		return url
	return url2pathname(parsed.path)

def dirname(url):
	scheme, path = splitscheme(url)
	parent = str(PurePosixPath(path).parent) if path else ''
	if parent == '.':
		parent = ''
	return scheme + parent

def basename(url):
	path = splitscheme(url)[1]
	return PurePosixPath(path).name if path else ''

def split(url):
	scheme, path = splitscheme(url)
	head, tail = os.path.split(path)
	return scheme + head, tail

def join(url, *paths):
	scheme, path = splitscheme(url)
	return scheme + PurePosixPath(path, *paths).as_posix()

def relpath(target, base):
	base = urlparse(base)
	target = urlparse(target)
	if base.scheme != target.scheme:
		raise ValueError(
			"Cannot construct a relative path across different URL schemes "
			"(%s -> %s)" % (base.scheme, target.scheme)
		)
	if base.netloc != target.netloc:
		raise ValueError(
			"Cannot construct a relative path across different URL net "
			"locations (%r != %r)" % (target.netloc, base.netloc)
		)

	base_dir = '.' + base.path
	target = '.' + target.path
	return posixpath.relpath(target, start=base_dir)