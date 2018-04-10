from concurrent.futures import ThreadPoolExecutor
from fman.impl.model.drag_and_drop import DragAndDrop
from fman.impl.model.diff import ComputeDiff
from fman.impl.model.file_watcher import FileWatcher
from fman.impl.model.table import TableModel, Cell, Row
from fman.impl.util.qt import EditRole, AscendingOrder
from fman.impl.util.qt.thread import run_in_main_thread, is_in_main_thread
from fman.impl.util.url import get_existing_pardir, is_pardir
from fman.url import dirname, join
from PyQt5.QtCore import pyqtSignal, QSortFilterProxyModel, QVariant, \
	QModelIndex, Qt
from PyQt5.QtGui import QIcon, QPixmap

import sys

class FileSystemModel(TableModel, DragAndDrop):

	file_renamed = pyqtSignal(str, str)
	location_loaded = pyqtSignal(str)

	def __init__(self, fs, location, columns):
		super().__init__([column.display_name for column in columns])
		self._fs = fs
		self._location = location
		self._columns = columns
		self._sort_order = 0, True
		self._allow_reload = False
		self._file_watcher = FileWatcher(fs, self._on_file_changed)
		self._executor = ThreadPoolExecutor(max_workers=1)
		self._shutdown_requested = False
	def start(self, sort_col_index, ascending, callback):
		self._connect_signals()
		if is_in_main_thread():
			self._execute_async(
				self._init_rows, sort_col_index, ascending, callback
			)
		else:
			self._init_rows(sort_col_index, ascending, callback)
	def shutdown(self):
		self._shutdown_requested = True
		self._file_watcher.clear()
		self._executor.shutdown(wait=not is_in_main_thread())
	def row_is_loaded(self, i):
		return self._rows[i].is_loaded
	def sort_col_is_loaded(self, column, ascending):
		return all(
			self.get_sort_value(i, column, ascending) != _NOT_LOADED
			for i in range(self.rowCount())
		)
	def load_sort_col(self, column, ascending, callback):
		assert is_in_main_thread()
		self._execute_async(self._load_sort_col, column, ascending, callback)
	def _load_sort_col(self, column_index, ascending, callback):
		assert not is_in_main_thread()
		column = self._columns[column_index]
		loaded = {}
		while True:
			to_load = self._on_sort_col_loaded(column_index, ascending, loaded)
			if not to_load:
				break
			for url in to_load:
				loaded[url] = column.get_sort_value(url, ascending)
		callback()
	@run_in_main_thread
	def _on_sort_col_loaded(self, column_index, ascending, values):
		missing = [row.url for row in self._rows if row.url not in values]
		if missing:
			return missing
		new_rows = []
		for row in self._rows:
			cells = []
			for i, column in enumerate(row.cells):
				if i == column_index:
					if ascending:
						col_val_asc = values[row.url]
						col_val_desc = column.sort_value_desc
					else:
						col_val_asc = column.sort_value_asc
						col_val_desc = values[row.url]
				else:
					col_val_asc = column.sort_value_asc
					col_val_desc = column.sort_value_desc
				cells.append(Cell(
					column.str, col_val_asc, col_val_desc
				))
			new_rows.append(File(
				row.url, row.icon, row.is_dir, cells, row.is_loaded
			))
		self._on_reloaded(new_rows)
	def load_rows(self, rows, callback=None):
		assert is_in_main_thread()
		urls = [self._rows[i].url for i in rows]
		def _load_async():
			loaded_rows = [self._load_row(url) for url in urls]
			self._on_rows_loaded(loaded_rows, callback)
		self._execute_async(_load_async)
	@run_in_main_thread
	def _on_rows_loaded(self, rows, callback=None):
		for row in rows:
			self._on_row_loaded_for_reload(row)
		if callback is not None:
			callback()
	def _connect_signals(self):
		"""
		Consider the example where the user creates a directory. This is done
		by a command from a separate thread via the following steps:

			1. file system -> create directory
			2. pane -> place cursor at new directory

		The second step must be executed *after* the file system has created the
		directory and the file system model has been updated to include the new
		folder.

		To accommodate the above, we process file system events *synchronously*
		in the worker threads that trigger them. On the other hand, the thread
		safety of this class works by only performing changing operations in the
		main thread. To synchronize the two ends, we use @run_in_main_thread.
		"""
		self._fs.file_added.add_callback(self._on_file_added)
		self._fs.file_moved.add_callback(self._on_file_moved)
		self._fs.file_removed.add_callback(self._on_file_removed)
	def get_columns(self):
		return self._columns
	def get_location(self):
		return self._location
	def url(self, index):
		if not self._index_is_valid(index):
			raise ValueError("Invalid index")
		return self._rows[index.row()].url
	def find(self, url):
		for rownum, row in enumerate(self._rows):
			if row.url == url:
				break
		else:
			raise ValueError('%r is not in list' % url)
		return self.index(rownum, 0, QModelIndex())
	def setData(self, index, value, role):
		if role == EditRole:
			self.file_renamed.emit(self.url(index), value)
			return True
		return super().setData(index, value, role)
	def reload(self):
		if self._shutdown_requested:
			return
		if is_in_main_thread():
			self._execute_async(self._reload)
		else:
			self._reload()
	def _reload(self):
		assert not is_in_main_thread()
		if not self._allow_reload:
			return
		self._allow_reload = False
		try:
			self._fs.clear_cache(self._location)
			rows = []
			file_names = iter(self._fs.iterdir(self._location))
			while not self._shutdown_requested:
				try:
					file_name = next(file_names)
				except (StopIteration, OSError):
					break
				else:
					url = join(self._location, file_name)
					try:
						try:
							row_before = self._rows[self.find(url).row()]
						except ValueError:
							row = self._init_row(url, *self._sort_order)
						else:
							if row_before.is_loaded:
								row = self._load_row(url)
							else:
								row = self._init_row(url, *self._sort_order)
					except FileNotFoundError:
						continue
					rows.append(row)
			else:
				assert self._shutdown_requested
				return
			self._on_reloaded(rows)
		finally:
			self._allow_reload = True
	@run_in_main_thread
	def _on_reloaded(self, rows):
		if self._shutdown_requested:
			return
		self.set_rows(rows)
		self._check_no_duplicate_rows()
	def get_sort_value(self, row, column, is_ascending):
		col = self._rows[row].cells[column]
		return col.sort_value_asc if is_ascending else col.sort_value_desc
	def _init_rows(self, sort_col_index, ascending, callback):
		assert not is_in_main_thread()
		if self._shutdown_requested:
			return
		self._sort_order = sort_col_index, ascending
		rows = []
		file_names = iter(self._fs.iterdir(self._location))
		while not self._shutdown_requested:
			try:
				file_name = next(file_names)
			except (StopIteration, OSError):
				break
			else:
				url = join(self._location, file_name)
				try:
					row = self._init_row(url, sort_col_index, ascending)
				except OSError:
					continue
				rows.append(row)
		else:
			assert self._shutdown_requested
			return
		if rows:
			self._on_rows_inited(rows)
		# Set _allow_reload before invoking callback so it can issue reloads:
		self._allow_reload = True
		# Invoke the callback before emitting location_loaded. The reason is
		# that the default location_loaded handler places the cursor - if is has
		# not been placed yet. If the callback does place it, ugly "flickering"
		# effects happen because first the callback and then location_loaded
		# change the cursor position.
		callback()
		self._on_location_loaded()
	def _init_row(self, url, sort_col_index, ascending):
		cells = []
		for i, column in enumerate(self._columns):
			# Load the first column because it is used as an
			# "anchor" when the user types in arbitrary characters:
			if i == 0:
				str_ = column.get_str(url)
			else:
				str_ = ''
			# Load the current sort value:
			sort_val_asc = sort_val_desc = _NOT_LOADED
			if i == sort_col_index:
				sort_value = column.get_sort_value(url, ascending)
				if ascending:
					sort_val_asc = sort_value
				else:
					sort_val_desc = sort_value
			cells.append(Cell(str_, sort_val_asc, sort_val_desc))
		return File(url, _get_empty_icon(), False, cells, False)
	def _load_row(self, url):
		try:
			is_dir = self._fs.is_dir(url)
		except OSError:
			is_dir = False
		icon = self._fs.icon(url) or _get_empty_icon()
		return File(
			url, icon, is_dir,
			[
				Cell(
					column.get_str(url),
					column.get_sort_value(url, True),
					column.get_sort_value(url, False)
				)
				for column in self._columns
			],
			True
		)
	@run_in_main_thread
	def _on_rows_inited(self, rows):
		self.insert_rows(rows)
		self._check_no_duplicate_rows()
	def _on_location_loaded(self):
		if self._shutdown_requested:
			return
		try:
			self._file_watcher.watch(self._location)
		except FileNotFoundError:
			# Looks like our location was deleted just after we finished
			# loading. Trust the rest of the implementation to handle this:
			pass
		else:
			self.location_loaded.emit(self._location)
	def _on_file_added(self, url):
		assert not is_in_main_thread()
		if self._is_in_root(url):
			try:
				row = self._load_row(url)
			except FileNotFoundError:
				return
			self._on_row_loaded_for_add(row)
	@run_in_main_thread
	def _on_row_loaded_for_add(self, row):
		if self._is_in_root(row.url):
			self._on_rows_inited([row])
	def _on_file_moved(self, old_url, new_url):
		assert not is_in_main_thread()
		if self._is_in_root(new_url):
			try:
				# It's important that we only attempt to load the row if it is
				# in the current root. The reason for this is that if the new
				# URL has a different scheme://, we might be loading the columns
				# from the current scheme for the new one, which may not support
				# them.
				row = self._load_row(new_url)
			except FileNotFoundError:
				row = None
		else:
			row = None
		self._on_row_moved(old_url, row)
	@run_in_main_thread
	def _on_row_moved(self, old_url, row=None):
		"""
		We don't just remove the old row and add the new one because this
		destroys the cursor state.
		"""
		is_in_root = False if row is None else self._is_in_root(row.url)
		try:
			rownum = self.find(old_url).row()
		except ValueError:
			if is_in_root:
				self._on_rows_inited([row])
		else:
			if is_in_root:
				self.update_rows([row], rownum)
				self._check_no_duplicate_rows()
			else:
				self.remove_rows(rownum)
	@run_in_main_thread
	def _on_file_removed(self, url):
		try:
			rownum = self.find(url).row()
		except ValueError:
			pass
		else:
			self.remove_rows(rownum)
	def _on_file_changed(self, url):
		assert is_in_main_thread()
		if url == self._location:
			# The common case
			self.reload()
		elif self._is_in_root(url):
			self._execute_async(self._reload_row, url)
	def _reload_row(self, url):
		assert not is_in_main_thread()
		if self._is_in_root(url): # Root could have changed in the meantime
			try:
				row = self._load_row(url)
			except FileNotFoundError:
				self._on_file_removed(url)
			else:
				self._on_row_loaded_for_reload(row)
	@run_in_main_thread
	def _on_row_loaded_for_reload(self, row):
		try:
			index = self.find(row.url)
		except ValueError:
			pass
		else:
			self.update_rows([row], index.row())
			self._check_no_duplicate_rows()
	def _check_no_duplicate_rows(self):
		assert len({r.url for r in self._rows}) == len(self._rows), \
			"Invariant violated: Duplicate rows."
	def _execute_async(self, fn, *args, **kwargs):
		future = self._executor.submit(fn, *args, **kwargs)
		future.add_done_callback(self._handle_async_exc)
	def _handle_async_exc(self, future):
		"""
		Python's ThreadPoolExecutor is awfully quiet about exceptions - both
		those that occur in the function passed to .submit(...), as well as
		those in the function passed to .add_done_callback(...).

		This method ensures that no exception goes unreported.
		"""
		# It would be tempting to simply do `future.result()` here. But this
		# crashes the thread for Python's ThreadPoolExecutor and results in it
		# logging "CRITICAL:concurrent.futures:Exception in worker". So we defer
		# to sys.excepthook(...) instead.
		exc = future.exception()
		if exc:
			sys.excepthook(type(exc), exc, exc.__traceback__)
	def _is_in_root(self, url):
		return dirname(url) == self._location
	def __str__(self):
		return '<%s: %s>' % (self.__class__.__name__, self._location)

_NOT_LOADED = object()

class SortedFileSystemModel(QSortFilterProxyModel):

	location_changed = pyqtSignal(str)
	location_loaded = pyqtSignal(str)
	file_renamed = pyqtSignal(str, str)
	files_dropped = pyqtSignal(list, str, bool)
	sort_order_changed = pyqtSignal(int, int)

	def __init__(self, parent, fs, null_location):
		super().__init__(parent)
		self._fs = fs
		self._null_location = null_location
		self._filters = []
		self._already_visited = set()
		self._sort_order = None, Qt.AscendingOrder
		self.set_location(null_location)
		self._fs.file_removed.add_callback(self._on_file_removed)
	def set_location(self, url, sort_column='', ascending=True, callback=None):
		if callback is None:
			callback = lambda: None
		url = self._fs.resolve(url)
		columns = self._fs.get_columns(url)
		if sort_column:
			column_names = [col.get_qualified_name() for col in columns]
			sort_col_index = column_names.index(sort_column)
		else:
			sort_col_index = 0
		old_model = self.sourceModel()
		if old_model:
			if url == old_model.get_location():
				callback()
				return
			old_model.shutdown()
		if url in self._already_visited:
			orig_callback = callback
			def callback():
				orig_callback()
				self.reload()
		self._set_location(url, columns, sort_col_index, ascending, callback)
	@run_in_main_thread
	def _set_location(self, url, columns, sort_col_index, ascending, callback):
		old_model = self.sourceModel()
		if old_model:
			self._disconnect_signals(old_model)
		new_model = FileSystemModel(self._fs, url, columns)
		self.setSourceModel(new_model)
		# At this point, we're "loaded" with an empty source model. Before we
		# actually start loading, set the sort column to ensure that this proxy
		# model doesn't accidentally query the wrong sort value as rows are
		# being inserted.
		self.sort(
			sort_col_index,
			Qt.AscendingOrder if ascending else Qt.DescendingOrder
		)
		self._connect_signals(new_model)
		new_model.start(sort_col_index, ascending, callback)
		self._already_visited.add(url)
		self.location_changed.emit(url)
	def row_is_loaded(self, i):
		source_row = self.mapToSource(self.index(i, 0)).row()
		return self.sourceModel().row_is_loaded(source_row)
	def load_rows(self, rows, callback=None):
		source_rows = [self._map_row_to_source(row) for row in rows]
		self.sourceModel().load_rows(source_rows, callback)
	def _map_row_to_source(self, i):
		return self.mapToSource(self.index(i, 0)).row()
	def get_location(self):
		return self.sourceModel().get_location()
	def get_columns(self):
		return self.sourceModel().get_columns()
	def reload(self):
		self.sourceModel().reload()
	def sort(self, column, order=Qt.AscendingOrder):
		assert is_in_main_thread()
		sort_order = column, order
		if sort_order == self._sort_order:
			return
		self._sort_order = sort_order
		source = self.sourceModel()
		ascending = order == Qt.AscendingOrder
		source._sort_order = column, ascending
		super_sort = super().sort
		sort = lambda: super_sort(*sort_order)
		if source.sort_col_is_loaded(column, ascending):
			sort()
			self.sort_order_changed.emit(*sort_order)
		else:
			def callback():
				run_in_main_thread(sort)()
				self.sort_order_changed.emit(*sort_order)
			source.load_sort_col(column, ascending, callback)
	def lessThan(self, left, right):
		source = self.sourceModel()
		is_ascending = self.sortOrder() == AscendingOrder
		def get_sort_value(l_r):
			return source.get_sort_value(l_r.row(), l_r.column(), is_ascending)
		return get_sort_value(left) < get_sort_value(right)
	def filterAcceptsRow(self, source_row, source_parent):
		source = self.sourceModel()
		url = source.url(source.index(source_row, 0, source_parent))
		for filter_ in self._filters:
			if not filter_(url):
				return False
		return True
	def add_filter(self, filter_):
		self._filters.append(filter_)
	def url(self, index):
		return self.sourceModel().url(self.mapToSource(index))
	def find(self, url):
		return self.mapFromSource(self.sourceModel().find(url))
	def _on_file_removed(self, url):
		if is_pardir(url, self.get_location()):
			existing_pardir = get_existing_pardir(url, self._fs.is_dir)
			self.set_location(existing_pardir or self._null_location)
	def _connect_signals(self, model):
		# Would prefer signal.connect(self.signal.emit) here. But PyQt doesn't
		# support it. So we need Python wrappers "_emit_...":
		model.location_loaded.connect(self._emit_location_loaded)
		model.file_renamed.connect(self._emit_file_renamed)
		model.files_dropped.connect(self._emit_files_dropped)
	def _disconnect_signals(self, model):
		# Would prefer signal.disconnect(self.signal.emit) here. But PyQt
		# doesn't support it. So we need Python wrappers "_emit_...":
		model.location_loaded.disconnect(self._emit_location_loaded)
		model.file_renamed.disconnect(self._emit_file_renamed)
		model.files_dropped.disconnect(self._emit_files_dropped)
	def _emit_location_loaded(self, location):
		self.location_loaded.emit(location)
	def _emit_file_renamed(self, old, new):
		self.file_renamed.emit(old, new)
	def _emit_files_dropped(self, urls, dest, is_copy):
		self.files_dropped.emit(urls, dest, is_copy)
	def __str__(self):
		return '<%s: %s>' % (self.__class__.__name__, self._location)

class File(Row):
	def __init__(self, url, icon, is_dir, cells, is_loaded):
		super().__init__(url, icon, is_dir, cells)
		self.is_loaded = is_loaded
	@property
	def url(self):
		return self.key
	@property
	def is_dir(self):
		return self.drop_enabled

@run_in_main_thread
def _get_empty_icon(size=128):
	"""
	It would be tempting to simply use `None` as an "empty" icon. But when we do
	this, Qt does not reserve the space usually taken up by the icon. (It's like
	display:none vs visibility:hidden in CSS.) This leads to ugly shifting
	effects as rows are loaded and the "empty" icon is replaced by a real one.
	To avoid this, our "empty" icon is in fact a transparent placeholder.

	The reason why this is a getter instead of a global variable is that we
	can't instantiate QPixmap at the module level. This is because QPixmap(...)
	requires a QApplication, which has not yet been instantiated at import time.
	"""
	global _empty_icon
	if _empty_icon is None:
		pixmap = QPixmap(size, size)
		pixmap.fill(Qt.transparent)
		_empty_icon = QIcon(pixmap)
	return _empty_icon

_empty_icon = None