from fman.fs import FileSystem, cached
from fman.impl.util import filenotfounderror
from fman.impl.util.path import resolve
from fman.url import splitscheme, basename, dirname
from io import UnsupportedOperation

class StubFileSystem(FileSystem):

	scheme = 'stub://'

	def __init__(self, items, default_columns=('core.Name',)):
		super().__init__()
		self._items = items
		self._default_columns = default_columns
	def get_default_columns(self, path):
		return self._default_columns
	def exists(self, path):
		return resolve(path) in self._items
	def iterdir(self, path):
		return list(self._items[resolve(path)].get('files', []))
	@cached # Mirror a typical implementation
	def is_dir(self, existing_path):
		path_resolved = resolve(existing_path)
		try:
			item = self._items[path_resolved]
		except KeyError:
			raise filenotfounderror(existing_path)
		return item.get('is_dir', False)
	@cached # Mirror a typical implementation
	def size_bytes(self, path):
		return self._items[resolve(path)].get('size', 1)
	@cached # Mirror a typical implementation
	def modified_datetime(self, path):
		return self._items[resolve(path)].get('mtime', 1473339041.0)
	def touch(self, path):
		self._items[resolve(path)] = {}
	def mkdir(self, path):
		self._items[resolve(path)] = {'is_dir': True}
	def move(self, src_url, dst_url):
		src_scheme, src_path = splitscheme(src_url)
		dst_scheme, dst_path = splitscheme(dst_url)
		if src_scheme != self.scheme or dst_scheme != self.scheme:
			raise UnsupportedOperation()
		self._items[resolve(dst_path)] = self._items.pop(resolve(src_path))
	def delete(self, path):
		path = resolve(path)
		new_items = {
			other_path: value for other_path, value in self._items.items()
			if other_path != path and not other_path.startswith(path)
		}
		self._items.clear()
		self._items.update(new_items)
		url = self.scheme + path
		parent, file_ = splitscheme(dirname(url))[1], basename(url)
		self._items[parent]['files'].remove(file_)