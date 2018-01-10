from fman.impl.util import Event, CachedIterator, filenotfounderror
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
		# Keep track of children being deleted so file_removed listeners can
		# call remove_file_changed_callback(...):
		self._children_being_deleted = {}
		self._icon_provider = icon_provider
		self._columns = {}
		self._cache = {}
		self._cache_locks = WeakValueDictionary()
	def add_child(self, scheme, instance):
		self._children[scheme] = instance
	def remove_child(self, scheme):
		self._children_being_deleted[scheme] = self._children.pop(scheme)
		self._cache = {
			url: value for url, value in self._cache.items()
			if not splitscheme(url)[0] == scheme
		}
		self.file_removed.trigger(scheme)
		del self._children_being_deleted[scheme]
	def register_column(self, column_name, column):
		self._columns[column_name] = column
	def unregister_column(self, column_name):
		del self._columns[column_name]
	def get_columns(self, url):
		child, path = self._split(url)
		child_get_cols = child.get_default_columns
		column_names = child_get_cols(path)
		try:
			return tuple(self._columns[name] for name in column_names)
		except KeyError as e:
			available_columns = ', '.join(map(repr, self._columns))
			fn_descr = child_get_cols.__qualname__.replace('.', '#') + '(...)'
			message = '%s returned a column that does not exist: %r. ' \
					  'Should have been one of %s.' % \
					  (fn_descr, e.args[0], available_columns)
			raise KeyError(message) from None
	def exists(self, url):
		return self._query(url, 'exists')
	def iterdir(self, url):
		return self._query_cache(url, 'iterdir')
	def query(self, url, fs_method_name):
		return self._query_cache(url, fs_method_name)
	def is_dir(self, existing_url):
		return self._query_cache(existing_url, 'is_dir')
	def icon(self, url):
		return self._query_cache(url, 'icon', self._icon_provider.get_icon)
	def touch(self, url):
		child, path = self._split(url)
		with TriggerFileAdded(self, url):
			child.touch(path)
	def mkdir(self, url):
		child, path = self._split(url)
		with TriggerFileAdded(self, url):
			child.mkdir(path)
	def makedirs(self, url, exist_ok=True):
		child, path = self._split(url)
		with TriggerFileAdded(self, url):
			child.makedirs(path, exist_ok=exist_ok)
	def move(self, src_url, dst_url):
		"""
		:param dst_url: must be the final destination url, not just the parent
		                directory.
		"""
		src_fs, src_path = self._split(src_url)
		dst_fs, dst_path = self._split(dst_url)
		try:
			src_fs.move(src_url, dst_url)
		except UnsupportedOperation:
			if src_fs == dst_fs:
				raise
			else:
				# Maybe the destination FS can handle the operation:
				dst_fs.move(src_url, dst_url)
		self._remove(src_url)
		self._add_to_parent(dst_url)
		self.file_moved.trigger(src_url, dst_url)
	def move_to_trash(self, url):
		child, path = self._split(url)
		child.move_to_trash(path)
		self._remove(url)
		self.file_removed.trigger(url)
	def delete(self, url):
		child, path = self._split(url)
		child.delete(path)
		self._remove(url)
		self.file_removed.trigger(url)
	def resolve(self, url):
		child, path = self._split(url)
		return child.resolve(path)
	def samefile(self, url1, url2):
		fs_1, path_1 = self._split(self.resolve(url1))
		fs_2, path_2 = self._split(self.resolve(url2))
		return fs_1 == fs_2 and fs_1.samefile(path_1, path_2)
	def copy(self, src_url, dst_url):
		src_fs, src_path = self._split(src_url)
		dst_fs, dst_path = self._split(dst_url)
		with TriggerFileAdded(self, dst_url):
			try:
				src_fs.copy(src_url, dst_url)
			except UnsupportedOperation:
				if src_fs == dst_fs:
					raise
				else:
					# Maybe the destination FS can handle the operation:
					dst_fs.copy(src_url, dst_url)
	def add_file_changed_callback(self, url, callback):
		child, path = self._split(url)
		child._add_file_changed_callback(path, callback)
	def remove_file_changed_callback(self, url, callback):
		scheme, path = splitscheme(url)
		try:
			child = self._children[scheme]
		except KeyError:
			try:
				child = self._children_being_deleted[scheme]
			except KeyError:
				raise filenotfounderror(url)
		child._remove_file_changed_callback(path, callback)
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
			try:
				return cache[prop]
			except KeyError:
				try:
					value = get_default(url)
				except Exception as e:
					if not cache:
						try:
							del self._cache[url]
						except KeyError:
							# This can for instance happen when clear_cache(...)
							# was called, or when another prop was
							# (unsuccessfully) queried from another thread. In
							# either case, it's fine that the cache was cleared.
							pass
					raise e from None
				try:
					value = CachedIterator(value)
				except TypeError as not_an_iterable:
					pass
				cache[prop] = value
				return value
	def _query(self, url, prop):
		child, path = self._split(url)
		return getattr(child, prop)(path)
	def _split(self, url):
		scheme, path = splitscheme(url)
		try:
			child = self._children[scheme]
		except KeyError:
			raise filenotfounderror(url)
		return child, path
	def _remove(self, url):
		self._cache = {
			other_url: value for other_url, value in self._cache.items()
			if other_url != url and not other_url.startswith(url + '/')
		}
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
			parent_files.append(basename(url))
	def _lock(self, url, item):
		return self._cache_locks.setdefault((url, item), Lock())

class TriggerFileAdded:
	def __init__(self, fs, url):
		self._fs = fs
		self._url = url
		self._file_existed = None
	def __enter__(self):
		self._file_existed = self._fs.exists(self._url)
	def __exit__(self, exc_type, exc_val, exc_tb):
		if not exc_val:
			self._fs._add_to_parent(self._url)
			if not self._file_existed:
				self._fs.file_added.trigger(self._url)