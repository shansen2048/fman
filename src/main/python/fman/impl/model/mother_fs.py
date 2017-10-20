from fman.util import Event
from os.path import dirname
from threading import Lock
from weakref import WeakValueDictionary

class MotherFileSystem:
	def __init__(self, source, icon_provider):
		super().__init__()
		self.file_added = Event()
		self.file_renamed = Event()
		self.file_removed = Event()
		self._source = source
		self._icon_provider = icon_provider
		self._cache = {}
		self._cache_locks = WeakValueDictionary()
	def exists(self, path):
		if path in self._cache:
			return True
		return self._source.exists(path)
	def listdir(self, path):
		result = self._query_cache(path, 'files', self._source.listdir)
		# Provide a copy of the list to ensure the caller doesn't accidentally
		# modify the state shared with other invocations:
		return result[::]
	def isdir(self, path):
		return self._query_cache(path, 'isdir', self._source.isdir)
	def getsize(self, path):
		return self._query_cache(path, 'size', self._source.getsize)
	def getmtime(self, path):
		return self._query_cache(path, 'mtime', self._source.getmtime)
	def icon(self, path):
		return self._query_cache(path, 'icon', self._icon_provider.get_icon)
	def touch(self, path):
		self._source.touch(path)
		if path not in self._cache:
			self._add_to_parent(path)
			self.file_added.trigger(path)
	def mkdir(self, path):
		self._source.mkdir(path)
		if path not in self._cache:
			self._add_to_parent(path)
			self.file_added.trigger(path)
	def rename(self, old_path, new_path):
		"""
		:param new_path: must be the final destination path, not just the parent
		                 directory.
		"""
		self._source.rename(old_path, new_path)
		try:
			self._cache[new_path] = self._cache.pop(old_path)
		except KeyError:
			pass
		self._remove_from_parent(old_path)
		self._add_to_parent(new_path)
		self.file_renamed.trigger(old_path, new_path)
	def move_to_trash(self, path):
		self._source.move_to_trash(path)
		self._remove(path)
		self.file_removed.trigger(path)
	def delete(self, path):
		self._source.delete(path)
		self._remove(path)
		self.file_removed.trigger(path)
	def add_file_changed_callback(self, path, callback):
		self._source._add_file_changed_callback(path, callback)
	def remove_file_changed_callback(self, path, callback):
		self._source._remove_file_changed_callback(path, callback)
	def clear_cache(self, path):
		try:
			del self._cache[path]
		except KeyError:
			pass
	def _query_cache(self, path, item, get_default):
		# We exploit the fact that setdefault is an atomic operation to avoid
		# having to lock the entire path in addition to (path, item).
		cache = self._cache.setdefault(path, {})
		with self._lock(path, item):
			if item not in cache:
				try:
					cache[item] = get_default(path)
				except:
					if not cache:
						del self._cache[path]
					raise
			return cache[item]
	def _remove(self, path):
		try:
			del self._cache[path]
		except KeyError:
			pass
		self._remove_from_parent(path)
	def _remove_from_parent(self, path):
		try:
			self._cache[dirname(path)]['files'].remove(path)
		except (KeyError, ValueError):
			pass
	def _add_to_parent(self, path):
		try:
			self._cache[dirname(path)]['files'].append(path)
		except KeyError:
			pass
	def _lock(self, path, item=None):
		return self._cache_locks.setdefault((path, item), Lock())
	def _on_source_file_changed(self, path):
		self.clear_cache(path)