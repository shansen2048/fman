from fman.url import dirname, splitscheme
from fman.util import Event
from functools import partial
from os.path import dirname
from threading import Lock
from weakref import WeakValueDictionary

class MotherFileSystem:
	def __init__(self, children, icon_provider):
		super().__init__()
		self.file_added = Event()
		self.file_renamed = Event()
		self.file_removed = Event()
		self._children = {child.scheme: child for child in children}
		self._icon_provider = icon_provider
		self._cache = {}
		self._cache_locks = WeakValueDictionary()
	def exists(self, url):
		if url in self._cache:
			return True
		return self._query(url, 'exists')
	def listdir(self, url):
		result = self._query_cache(url, 'listdir')
		# Provide a copy of the list to ensure the caller doesn't accidentally
		# modify the state shared with other invocations:
		return result[::]
	def isdir(self, url):
		return self._query_cache(url, 'isdir')
	def getsize(self, url):
		return self._query_cache(url, 'getsize')
	def getmtime(self, url):
		return self._query_cache(url, 'getmtime')
	def icon(self, url):
		return self._query_cache(url, 'icon', self._get_icon)
	def _get_icon(self, url):
		scheme, path = splitscheme(url)
		if scheme != 'file://':
			raise ValueError("URL %r is not supported" % url)
		return self._icon_provider.get_icon(path)
	def touch(self, url):
		scheme, path = splitscheme(url)
		self._children[scheme].touch(path)
		if url not in self._cache:
			self._add_to_parent(url)
			self.file_added.trigger(url)
	def mkdir(self, url):
		scheme, path = splitscheme(url)
		self._children[scheme].mkdir(path)
		if url not in self._cache:
			self._add_to_parent(url)
			self.file_added.trigger(url)
	def rename(self, old_url, new_url):
		"""
		:param new_url: must be the final destination url, not just the parent
		                directory.
		"""
		old_scheme, old_path = splitscheme(old_url)
		new_scheme, new_path = splitscheme(new_url)
		if old_scheme != new_scheme:
			raise ValueError(
				'Renaming across file systems is not supported (%s -> %s)'
				% (old_scheme, new_scheme)
			)
		self._children[old_scheme].rename(old_path, new_path)
		try:
			self._cache[new_url] = self._cache.pop(old_url)
		except KeyError:
			pass
		self._remove_from_parent(old_url)
		self._add_to_parent(new_url)
		self.file_renamed.trigger(old_url, new_url)
	def move_to_trash(self, url):
		scheme, path = splitscheme(url)
		self._children[scheme].move_to_trash(path)
		self._remove(url)
		self.file_removed.trigger(url)
	def delete(self, url):
		scheme, path = splitscheme(url)
		self._children[scheme].delete(path)
		self._remove(url)
		self.file_removed.trigger(url)
	def resolve(self, url):
		scheme, path = splitscheme(url)
		return scheme + self._children[scheme].resolve(path)
	def add_file_changed_callback(self, url, callback):
		scheme, path = splitscheme(url)
		self._children[scheme]._add_file_changed_callback(path, callback)
	def remove_file_changed_callback(self, url, callback):
		scheme, path = splitscheme(url)
		self._children[scheme]._remove_file_changed_callback(path, callback)
	def clear_cache(self, url):
		try:
			del self._cache[url]
		except KeyError:
			pass
	def _query_cache(self, url, prop, get_default=None):
		if get_default is None:
			get_default = partial(self._query, prop=prop)
		# We exploit the fact that setdefault is an atomic operation to avoid
		# having to lock the entire url in addition to (url, item).
		cache = self._cache.setdefault(url, {})
		with self._lock(url, prop):
			if prop not in cache:
				try:
					cache[prop] = get_default(url)
				except:
					if not cache:
						del self._cache[url]
					raise
			return cache[prop]
	def _query(self, url, prop):
		scheme, path = splitscheme(url)
		child = self._children[scheme]
		return getattr(child, prop)(path)
	def _remove(self, url):
		try:
			del self._cache[url]
		except KeyError:
			pass
		self._remove_from_parent(url)
	def _remove_from_parent(self, url):
		try:
			self._cache[dirname(url)]['listdir'].remove(url)
		except (KeyError, ValueError):
			pass
	def _add_to_parent(self, url):
		try:
			self._cache[dirname(url)]['listdir'].append(url)
		except KeyError:
			pass
	def _lock(self, path, item=None):
		return self._cache_locks.setdefault((path, item), Lock())
	def _on_source_file_changed(self, path):
		self.clear_cache(path)