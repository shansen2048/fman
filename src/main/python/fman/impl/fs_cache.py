from threading import RLock, Lock
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
				try:
					result = CachedIterator(result)
				except TypeError as not_an_iterator:
					pass
				self._items.setdefault(path, {})[attr] = result
				return result
	def delete(self, path):
		self._items = {
			other_path: value for other_path, value in self._items.items()
			if other_path != path and not other_path.startswith(path + '/')
		}
	def _lock(self, path, attr):
		return self._locks.setdefault((path, attr), RLock())

class CachedIterator:

	_DELETED = object()

	def __init__(self, source):
		"""
		This constructor must(!) raise `TypeError` if source is not an iterator.
		"""
		if not hasattr(source, '__next__'):
			raise TypeError('Not an iterator: %r' % source)
		self._source = source
		self._lock = Lock()
		self._items = []
		self._items_to_skip = []
		self._items_to_add = []
	def remove(self, item):
		try:
			item_index = self._items.index(item)
		except ValueError:
			self._items_to_skip.append(item)
		else:
			self._items[item_index] = self._DELETED
	def append(self, item):
		# N.B.: Behaves like set#add(...), not like list#append(...)!
		self._items_to_add.append(item)
	def __iter__(self):
		return _CachedIterator(self)
	def get_next(self, pointer):
		with self._lock:
			for pointer in range(pointer, len(self._items)):
				item = self._items[pointer]
				if item is not self._DELETED:
					return pointer + 1, item
			return pointer + 1, self._generate_next()
	def _generate_next(self):
		while True:
			try:
				result = next(self._source)
			except StopIteration:
				for i, result in enumerate(self._items_to_add):
					if result not in self._items:
						self._items_to_add = self._items_to_add[i + 1:]
						break
				else:
					raise
			if self._items_to_skip and result == self._items_to_skip[0]:
				self._items_to_skip.pop(0)
			else:
				self._items.append(result)
				return result

class _CachedIterator:
	def __init__(self, parent):
		self._parent = parent
		self._pointer = 0
	def __next__(self):
		self._pointer, result = self._parent.get_next(self._pointer)
		return result