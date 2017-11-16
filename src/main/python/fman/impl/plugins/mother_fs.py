from fman.impl.util import Event, CachedIterable
from fman.url import splitscheme, basename, dirname
from io import UnsupportedOperation
from functools import partial
from threading import Lock
from weakref import WeakValueDictionary

class MotherFileSystem:
	def __init__(self, icon_provider):
		super().__init__()
		self.file_added = Event()
		self.file_moved = Event()
		self.file_removed = Event()
		self._children = {}
		self._icon_provider = icon_provider
		self._columns = {}
		self._cache = {}
		self._cache_locks = WeakValueDictionary()
	def add_child(self, file_system):
		self._children[file_system.scheme] = file_system
	def register_column(self, column_name, column):
		self._columns[column_name] = column
	def get_columns(self, url):
		scheme, path = splitscheme(url)
		column_names = self._children[scheme].get_default_columns(path)
		return tuple(self._columns[name] for name in column_names)
	def exists(self, url):
		return self._query(url, 'exists')
	def iterdir(self, url):
		return self._query_cache(url, 'iterdir', self._iterdir)
	def _iterdir(self, url):
		return CachedIterable(self._query(url, 'iterdir'))
	def query(self, url, fs_method_name):
		return self._query_cache(url, fs_method_name)
	def is_dir(self, url):
		return self._query_cache(url, 'is_dir')
	def icon(self, url):
		return self._query_cache(url, 'icon', self._icon_provider.get_icon)
	def touch(self, url):
		scheme, path = splitscheme(url)
		with TriggerFileAdded(self, url):
			self._children[scheme].touch(path)
	def mkdir(self, url):
		scheme, path = splitscheme(url)
		with TriggerFileAdded(self, url):
			self._children[scheme].mkdir(path)
	def makedirs(self, url, exist_ok=True):
		scheme, path = splitscheme(url)
		with TriggerFileAdded(self, url):
			self._children[scheme].makedirs(path, exist_ok=exist_ok)
	def move(self, src_url, dst_url):
		"""
		:param dst_url: must be the final destination url, not just the parent
		                directory.
		"""
		src_scheme, src_path = splitscheme(src_url)
		dst_scheme, dst_path = splitscheme(dst_url)
		try:
			self._children[src_scheme].move(src_url, dst_url)
		except UnsupportedOperation:
			if src_scheme == dst_scheme:
				raise
			else:
				# Maybe the destination FS can handle the operation:
				self._children[dst_scheme].move(src_url, dst_url)
		try:
			self._cache[dst_url] = self._cache.pop(src_url)
		except KeyError:
			pass
		self._remove_from_parent(src_url)
		self._add_to_parent(dst_url)
		self.file_moved.trigger(src_url, dst_url)
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
	def samefile(self, url1, url2):
		scheme_1, path_1 = splitscheme(self.resolve(url1))
		scheme_2, path_2 = splitscheme(self.resolve(url2))
		if scheme_1 == scheme_2:
			return self._children[scheme_1].samefile(path_1, path_2)
		return False
	def copy(self, src_url, dst_url):
		src_scheme, src_path = splitscheme(src_url)
		dst_scheme, dst_path = splitscheme(dst_url)
		with TriggerFileAdded(self, dst_url):
			try:
				self._children[src_scheme].copy(src_url, dst_url)
			except UnsupportedOperation:
				if src_scheme == dst_scheme:
					raise
				else:
					# Maybe the destination FS can handle the operation:
					self._children[dst_scheme].copy(src_url, dst_url)
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
		parent = dirname(url)
		try:
			parent_files = self._cache[parent]['iterdir']
		except KeyError:
			pass
		else:
			try:
				parent_files.remove(basename(url))
			except ValueError:
				pass
	def _add_to_parent(self, url):
		parent = dirname(url)
		try:
			parent_files = self._cache[parent]['iterdir']
		except KeyError:
			pass
		else:
			parent_files.add(basename(url))
	def _lock(self, path, item=None):
		return self._cache_locks.setdefault((path, item), Lock())
	def _on_source_file_changed(self, path):
		self.clear_cache(path)

class TriggerFileAdded:
	def __init__(self, fs, url):
		self._fs = fs
		self._url = url
		self._file_existed = None
	def __enter__(self):
		self._file_existed = self._url in self._fs._cache
	def __exit__(self, exc_type, exc_val, exc_tb):
		if not exc_val:
			self._fs._add_to_parent(self._url)
			if not self._file_existed:
				self._fs.file_added.trigger(self._url)