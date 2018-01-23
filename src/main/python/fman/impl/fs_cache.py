from threading import RLock
from weakref import WeakValueDictionary

class Cache:
	def __init__(self):
		self._items = {}
		self._locks = WeakValueDictionary()
	def put(self, path, attr, value):
		self._items.setdefault(path, {})[attr] = value
	def get(self, path, attr):
		return self._items[path][attr]
	def query(self, path, attr, compute_value):
		with self._lock(path, attr):
			try:
				return self._items[path][attr]
			except KeyError:
				result = compute_value()
				self._items.setdefault(path, {})[attr] = result
				return result
	def delete(self, path):
		self._items = {
			other_path: value for other_path, value in self._items.items()
			if other_path != path and not other_path.startswith(path + '/')
		}
	def _lock(self, path, attr):
		return self._locks.setdefault((path, attr), RLock())