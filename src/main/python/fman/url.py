from pathlib import PurePath, PurePosixPath

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

def exists(url):
	return _get_fs().exists(url)

def touch(url):
	_get_fs().touch(url)

def mkdir(url):
	_get_fs().mkdir(url)

def isdir(url):
	return _get_fs().isdir(url)

def isfile(url):
	return _get_fs().isfile(url)

def getsize(url):
	return _get_fs().getsize(url)

def getmtime(url):
	return _get_fs().getmtime(url)

def rename(old_url, new_url):
	_get_fs().rename(old_url, new_url)

def move_to_trash(url):
	_get_fs().move_to_trash(url)

def delete(url):
	_get_fs().delete(url)

def parent(url):
	return _get_fs().parent(url)

def dirname(url):
	scheme, path = splitscheme(url)
	return scheme + (str(PurePosixPath(path).parent) if path else '')

def samefile(url_1, url_2):
	return _get_fs().samefile(url_1, url_2)

def join(url, *paths):
	scheme, path = splitscheme(url)
	return scheme + PurePosixPath(path, *paths).as_posix()

def _get_fs():
	from fman.impl.application_context import get_application_context
	return get_application_context().fs