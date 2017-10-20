class StubFileSystem:
	def __init__(self, items):
		self._items = items
	def exists(self, item):
		return item in self._items
	def listdir(self, item):
		return self._items[item].get('files', [])
	def isdir(self, item):
		return self._items[item].get('isdir', False)
	def getsize(self, item):
		return self._items[item].get('size', 1)
	def getmtime(self, item):
		return self._items[item].get('mtime', 1473339041.0)
	def touch(self, item):
		self._items[item] = {}
	def mkdir(self, item):
		self._items[item] = { 'isdir': True }
	def rename(self, old_path, new_path):
		self._items[new_path] = self._items.pop(old_path)
	def delete(self, item):
		del self._items[item]