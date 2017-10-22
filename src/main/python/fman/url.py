from pathlib import PurePosixPath, PurePath

def dirname(url):
	scheme, path = splitscheme(url)
	return scheme + str(PurePosixPath(path).parent)

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