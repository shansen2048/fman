def exists(url):
	return _get_fs().exists(url)

def touch(url):
	_get_fs().touch(url)

def mkdir(url):
	_get_fs().mkdir(url)

def makedirs(url, exist_ok=False):
	_get_fs().makedirs(url, exist_ok=exist_ok)

def is_dir(url):
	return _get_fs().is_dir(url)

def isfile(url):
	return _get_fs().isfile(url)

def getsize(url):
	return _get_fs().getsize(url)

def getmtime(url):
	return _get_fs().getmtime(url)

def move(old_url, new_url):
	_get_fs().move(old_url, new_url)

def move_to_trash(url):
	_get_fs().move_to_trash(url)

def delete(url):
	_get_fs().delete(url)

def parent(url):
	return _get_fs().parent(url)

def samefile(url_1, url_2):
	return _get_fs().samefile(url_1, url_2)

def copy(src, dst):
	_get_fs().copy(src, dst)

def iterdir(url):
	return _get_fs().iterdir(url)

def _get_fs():
	from fman.impl.application_context import get_application_context
	return get_application_context().fs