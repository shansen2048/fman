from fman.impl.model.fs import FileSystem

class StubFileSystem(FileSystem):

	scheme = 'stub://'

	def __init__(self, items):
		super().__init__()
		self._items = items
	def exists(self, path):
		return path in self._items
	def iterdir(self, path):
		return list(self._items[path].get('files', []))
	def isdir(self, path):
		try:
			return self._items[path]['isdir']
		except KeyError:
			return False
	def getsize(self, path):
		return self._items[path].get('size', 1)
	def getmtime(self, path):
		return self._items[path].get('mtime', 1473339041.0)
	def touch(self, path):
		self._items[path] = {}
	def mkdir(self, path):
		self._items[path] = {'isdir': True}
	def move(self, old_path, new_path):
		self._items[new_path] = self._items.pop(old_path)
	def delete(self, path):
		del self._items[path]