from fman.impl.util.path import parent
from fman.impl.util.url import resolve
from threading import Lock

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

def get_size_bytes(url):
	return _get_fs().get_size_bytes(url)

def get_modified_datetime(url):
	return _get_fs().get_modified_datetime(url)

def move(old_url, new_url):
	_get_fs().move(old_url, new_url)

def move_to_trash(url):
	_get_fs().move_to_trash(url)

def delete(url):
	_get_fs().delete(url)

def samefile(url_1, url_2):
	return _get_fs().samefile(url_1, url_2)

def copy(src, dst):
	_get_fs().copy(src, dst)

def iterdir(url):
	return _get_fs().iterdir(url)

class FileSystem:

	scheme = ''

	def __init__(self):
		self._file_changed_callbacks = {}
		self._file_changed_callbacks_lock = Lock()
	def iterdir(self, path):
		raise NotImplementedError()
	def resolve(self, path):
		return resolve(self.scheme + path)
	def watch(self, path):
		pass
	def unwatch(self, path):
		pass
	def notify_file_changed(self, path):
		for callback in self._file_changed_callbacks.get(path, []):
			callback(self.scheme + path)
	def samefile(self, f1, f2):
		return self.resolve(f1) == self.resolve(f2)
	def makedirs(self, path, exist_ok=True):
		# Copied / adapted from pathlib.Path#mkdir(...).
		try:
			self.mkdir(path)
		except FileExistsError:
			if not exist_ok or not self.is_dir(path):
				raise
		except FileNotFoundError:
			self.makedirs(parent(path))
			self.mkdir(path)
	def mkdir(self, path):
		"""
		Should raise FileExistsError if `path` already exists. If `path` is in
		a directory that does not yet exist, should raise a FileNotFoundError.
		"""
		raise NotImplementedError()
	def get_size_bytes(self, path):
		return None
	def get_modified_datetime(self, path):
		return None
	def _add_file_changed_callback(self, path, callback):
		with self._file_changed_callbacks_lock:
			try:
				self._file_changed_callbacks[path].append(callback)
			except KeyError:
				self._file_changed_callbacks[path] = [callback]
				self.watch(path)
	def _remove_file_changed_callback(self, path, callback):
		with self._file_changed_callbacks_lock:
			path_callbacks = self._file_changed_callbacks[path]
			path_callbacks.remove(callback)
			if not path_callbacks:
				del self._file_changed_callbacks[path]
				self.unwatch(path)

def _get_fs():
	from fman.impl.application_context import get_application_context
	return get_application_context().fs