from fman.fs import FileSystem
from fman.url import splitscheme
from io import UnsupportedOperation

class StubFileSystem(FileSystem):

	scheme = 'stub://'

	def __init__(self, items):
		super().__init__()
		self._items = items
	def exists(self, path):
		return path in self._items
	def iterdir(self, path):
		return list(self._items[path].get('files', []))
	def is_dir(self, path):
		try:
			return self._items[path]['is_dir']
		except KeyError:
			return False
	def get_size_bytes(self, path):
		return self._items[path].get('size', 1)
	def get_modified_datetime(self, path):
		return self._items[path].get('mtime', 1473339041.0)
	def touch(self, path):
		self._items[path] = {}
	def mkdir(self, path):
		self._items[path] = {'is_dir': True}
	def move(self, src_url, dst_url):
		src_scheme, src_path = splitscheme(src_url)
		dst_scheme, dst_path = splitscheme(dst_url)
		if src_scheme != self.scheme or dst_scheme != self.scheme:
			raise UnsupportedOperation()
		self._items[dst_path] = self._items.pop(src_path)
	def delete(self, path):
		self._items = {
			other_path: value for other_path, value in self._items.items()
			if other_path != path and not other_path.startswith(path)
		}