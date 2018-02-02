from threading import Lock, RLock
from weakref import WeakValueDictionary

class Cache:
	def __init__(self):
		self._items = {}
		"""
		We need a separate write lock to avoid spurious
			"RuntimeError: dictionary changed size during iteration"
		in clear(). The reason is that this method iterates over _items. If
		another method (such as put(...)) updates _items at the same time, the
		error occurs.
		"""
		self._write_lock = Lock()
		self._read_locks = WeakValueDictionary()
	def put(self, path, attr, value):
		with self._write_lock:
			self._items.setdefault(path, {})[attr] = value
	def get(self, path, attr):
		return self._items[path][attr]
	def query(self, path, attr, compute_value):
		with self._read_locks.setdefault((path, attr), RLock()):
			try:
				return self._items[path][attr]
			except KeyError:
				value = compute_value()
				self.put(path, attr, value)
				return value
	def clear(self, path):
		with self._write_lock:
			self._items = {
				other_path: value for other_path, value in self._items.items()
				if other_path != path and not other_path.startswith(path + '/')
			}