from fman.url import splitscheme, basename
from fman.util import Event
from functools import partial
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
		return self._query(url, 'exists')
	def listdir(self, url):
		result = self._query_cache(url, 'listdir')
		# Provide a copy of the list to ensure the caller doesn't accidentally
		# modify the state shared with other invocations:
		return result[::]
	def isdir(self, url):
		return self._query_cache(url, 'isdir')
	def isfile(self, url):
		return self._query_cache(url, 'isfile')
	def getsize(self, url):
		return self._query_cache(url, 'getsize')
	def getmtime(self, url):
		return self._query_cache(url, 'getmtime')
	def icon(self, url):
		return self._query_cache(url, 'icon', self._get_icon)
	def _get_icon(self, url):
		scheme, path = splitscheme(url)
		if scheme != 'file://':
			url = self.resolve(url)
			scheme, path = splitscheme(url)
			if scheme != 'file://':
				raise ValueError("URL %r is not supported" % url)
		return self._icon_provider.get_icon(path)
	def touch(self, url):
		scheme, path = splitscheme(url)
		self._children[scheme].touch(path)
		self._file_added(url)
	def mkdir(self, url):
		scheme, path = splitscheme(url)
		self._children[scheme].mkdir(path)
		self._file_added(url)
	def makedirs(self, url, exist_ok=True):
		scheme, path = splitscheme(url)
		self._children[scheme].makedirs(path, exist_ok=exist_ok)
		prev_url = None
		while url != prev_url:
			self._file_added(url)
			prev_url = url
			url = self.parent(url)
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
		return self._children[scheme].resolve(path)
	def parent(self, url):
		return self._query_cache(url, 'parent')
	def samefile(self, url_1, url_2):
		scheme_1, path_1 = splitscheme(self.resolve(url_1))
		scheme_2, path_2 = splitscheme(self.resolve(url_2))
		if scheme_1 == scheme_2:
			return self._children[scheme_1].samefile(path_1, path_2)
		return False
	def copy(self, src_url, dst_url):
		src_scheme, src_path = splitscheme(src_url)
		dst_scheme, dst_path = splitscheme(dst_url)
		if src_scheme != dst_scheme:
			raise ValueError(
				'Cannot copy from %s to %s' % (src_scheme, dst_scheme)
			)
		self._children[src_scheme].copy(src_path, dst_path)
		self._file_added(dst_url)
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
		parent = self.parent(url)
		try:
			parent_files = self._cache[parent]['listdir']
		except KeyError:
			pass
		else:
			try:
				parent_files.remove(basename(url))
			except ValueError:
				pass
	def _file_added(self, url):
		self._add_to_parent(url)
		if url not in self._cache:
			self.file_added.trigger(url)
	def _add_to_parent(self, url):
		parent = self.parent(url)
		try:
			parent_files = self._cache[parent]['listdir']
		except KeyError:
			pass
		else:
			name = basename(url)
			if name not in parent_files:
				parent_files.append(name)
	def _lock(self, path, item=None):
		return self._cache_locks.setdefault((path, item), Lock())
	def _on_source_file_changed(self, path):
		self.clear_cache(path)