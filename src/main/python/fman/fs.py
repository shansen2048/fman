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

def samefile(url_1, url_2):
	return _get_fs().samefile(url_1, url_2)

def _get_fs():
	from fman.impl.application_context import get_application_context
	return get_application_context().fs