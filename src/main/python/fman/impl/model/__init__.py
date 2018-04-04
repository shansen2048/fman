from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor
from fman.impl.model.drag_and_drop import DragAndDrop
from fman.impl.model.diff import ComputeDiff
from fman.impl.util import is_debug
from fman.impl.util.qt import ItemIsEnabled, ItemIsEditable, ItemIsSelectable, \
	EditRole, AscendingOrder, DisplayRole, ItemIsDragEnabled, \
	ItemIsDropEnabled, DecorationRole, ToolTipRole
from fman.impl.util.qt.thread import run_in_main_thread, is_in_main_thread
from fman.impl.util.url import get_existing_pardir, is_pardir
from fman.url import dirname, join
from PyQt5.QtCore import pyqtSignal, QSortFilterProxyModel, QVariant, \
	QModelIndex, Qt
from time import time

import sys

class PreloadedRow(
	namedtuple('PreloadedRow', ('url', 'is_dir', 'icon', 'columns'))
):
	"""
	The sole purpose of this subclass is to exclude .icon from == comparisons.
	The reason for this is that QFileIconProvider returns objects that don't
	compare equal even if they are equal. This is a problem particularly on
	Windows. For when we reload a directory, QFileIconProvider returns "new"
	icon values so our implementation must assume that all files in the
	directory have changed (when most likely they haven't).

	An earlier implementation used QIcon#cacheKey() in an attempt to solve the
	above problem. In theory, #cacheKey() is precisely meant to help with this.
	But in reality, especially on Windows, the problem remains (loading the icon
	of a file with QFileIconProvider twice gives two QIcon instances that look
	the same but have different cacheKey's).
	"""

	def _get_attrs_for_eq(self):
		# Note how .icon is not contained in this tuple:
		return self.url, self.is_dir, self.columns
	def __eq__(self, other):
		try:
			return self._get_attrs_for_eq() == other._get_attrs_for_eq()
		except AttributeError:
			return False
	def __ne__(self, other):
		return not self.__eq__(other)
	def __hash__(self):
		return hash(self._get_attrs_for_eq())

PreloadedColumn = \
	namedtuple('PreloadedColumn', ('str', 'sort_value_asc', 'sort_value_desc'))

class FileSystemModel(DragAndDrop):

	file_renamed = pyqtSignal(str, str)
	location_changed = pyqtSignal(str)
	location_loaded = pyqtSignal(str)

	def __init__(self, fs, null_location):
		super().__init__()
		self._fs = fs
		self._location = None # until we call set_location(...) below
		self._allow_reload = False
		self._already_visited = set()
		self._rows = []
		self._executor = ThreadPoolExecutor()
		self._columns = ()
		self._file_watcher = FileWatcher(fs, self._on_file_changed)
		self._connect_signals()
		self.set_location(null_location)
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
		self.location_loaded.connect(self._on_location_loaded)
	def rowCount(self, parent=QModelIndex()):
		if parent.isValid():
			# According to the Qt docs for QAbstractItemModel#rowCount(...):
			# "When implementing a table based model, columnCount() should
			#  return 0 when the parent is valid."
			return 0
		return len(self._rows)
	def columnCount(self, parent=QModelIndex()):
		if parent.isValid():
			# According to the Qt docs for QAbstractItemModel#columnCount(...):
			# "When implementing a table based model, columnCount() should
			#  return 0 when the parent is valid."
			return 0
		return len(self._columns)
	def data(self, index, role=DisplayRole):
		if self._index_is_valid(index):
			if role in (DisplayRole, EditRole):
				return self._rows[index.row()].columns[index.column()].str
			elif role == DecorationRole and index.column() == 0:
				return self._rows[index.row()].icon
			elif role == ToolTipRole and index.column() == 0:
				return super(FileSystemModel, self).data(index, DisplayRole)
		return QVariant()
	def headerData(self, section, orientation, role=DisplayRole):
		if orientation == Qt.Horizontal and role == DisplayRole \
			and 0 <= section < self.columnCount():
			return QVariant(self._columns[section].display_name)
		return QVariant()
	def get_columns(self):
		return self._columns
	def get_location(self):
		return self._location
	def set_location(self, url, callback=None):
		if callback is None:
			callback = lambda: None
		url = self._fs.resolve(url)
		if url == self._location:
			callback()
		else:
			self._file_watcher.clear()
			self._prepare_new_location(url)
			if is_in_main_thread():
				self._execute_async(self._load_rows, url, callback)
			else:
				self._load_rows(url, callback)
	@run_in_main_thread
	def _prepare_new_location(self, url):
		self._location = url
		self._allow_reload = False
		self.location_changed.emit(url)
		self.beginResetModel()
		self._rows = []
		self._columns = self._fs.get_columns(url)
		self.endResetModel()
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
	def flags(self, index):
		if index == QModelIndex():
			# The index representing our current location:
			return ItemIsDropEnabled
		# Need to set ItemIsEnabled - in particular for the last column - to
		# make keyboard shortcut "End" work. When we press this shortcut in a
		# QTableView, Qt jumps to the last column of the last row. But only if
		# this cell is enabled. If it isn't enabled, Qt simply does nothing.
		# So we set the cell to enabled.
		result = ItemIsSelectable | ItemIsEnabled
		if index.column() == 0:
			result |= ItemIsEditable | ItemIsDragEnabled
			if self._rows[index.row()].is_dir:
				result |= ItemIsDropEnabled
		return result
	def setData(self, index, value, role):
		if role == EditRole:
			self.file_renamed.emit(self.url(index), value)
			return True
		return super().setData(index, value, role)
	def reload(self, location=None):
		if location is None:
			location = self._location
		if is_in_main_thread():
			self._execute_async(self._reload, location)
		else:
			self._reload(location)
	def _reload(self, location):
		assert not is_in_main_thread()
		if not self._allow_reload:
			return
		self._allow_reload = False
		try:
			# Abort reload if path changed:
			if location != self._location:
				return
			self._fs.clear_cache(location)
			rows = []
			file_names = iter(self._fs.iterdir(location))
			while self._location == location: # Abort reload if location changed
				try:
					file_name = next(file_names)
				except (StopIteration, OSError):
					break
				else:
					file_url = join(location, file_name)
					try:
						rows.append(self._load_row(file_url))
					except FileNotFoundError:
						pass
			else:
				assert self._location != location
				return
			self._on_reloaded(location, rows)
		finally:
			self._allow_reload = True
	@run_in_main_thread
	def _on_reloaded(self, location, rows):
		# Abort reload if path changed:
		if location != self._location:
			return
		diff = ComputeDiff(self._rows, rows, key_fn=lambda row: row.url)()
		if is_debug():
			rows_before = list(self._rows)
		for entry in diff:
			entry.apply(
				self._insert_rows, self._move_rows, self._update_rows,
				self._remove_rows
			)
		self._check_no_duplicate_rows()
		if is_debug():
			assert self._rows == rows, \
				'Applying diff did not yield expected result.\n\n' \
				'Old rows:\n%r\n\n' \
				'New rows:\n%r\n\n' \
				'Diff:\n%r\n\n' \
				'Result of applying diff to old rows:\n%r' % \
				(rows_before, rows, diff, self._rows)
	def get_sort_value(self, row, column, is_ascending):
		col = self._rows[row].columns[column]
		return col.sort_value_asc if is_ascending else col.sort_value_desc
	def _index_is_valid(self, index):
		if not index.isValid() or index.model() != self:
			return False
		return 0 <= index.row() < self.rowCount() and \
			   0 <= index.column() < self.columnCount()
	def _load_rows(self, location, callback, update_interval_secs=0.25):
		assert not is_in_main_thread()
		if location != self._location:
			# Location changed since this method was scheduled. Abort.
			return
		batch = []
		last_update = time()
		file_names = iter(self._fs.iterdir(location))
		while self._location == location: # Abort if location changed
			try:
				file_name = next(file_names)
			except (StopIteration, OSError):
				break
			else:
				try:
					row = self._load_row(join(location, file_name))
				except FileNotFoundError:
					continue
				batch.append(row)
				if time() > last_update + update_interval_secs:
					self._on_rows_loaded(batch, location)
					batch = []
					last_update = time()
		else:
			assert self._location != location
			return
		if batch:
			self._on_rows_loaded(batch, location)
		# Invoke the callback before emitting location_loaded. The reason is
		# that the default location_loaded handler places the cursor - if is has
		# not been placed yet. If the callback does place it, ugly "flickering"
		# effects happen because first the callback and then location_loaded
		# change the cursor position.
		callback()
		self.location_loaded.emit(location)
		self._allow_reload = True
		# No point reloading if this is the first visit and the location was
		# thus just loaded.
		if location in self._already_visited:
			self.reload(location)
		self._already_visited.add(location)
	def _load_row(self, url):
		try:
			is_dir = self._fs.is_dir(url)
		except OSError:
			is_dir = False
		try:
			icon = self._fs.icon(url)
		except OSError:
			icon = None
		return PreloadedRow(
			url, is_dir, icon,
			[
				PreloadedColumn(
					QVariant(column.get_str(url)),
					column.get_sort_value(url, True),
					column.get_sort_value(url, False)
				)
				for column in self._columns
			]
		)
	@run_in_main_thread
	def _on_rows_loaded(self, rows, for_location=None):
		if for_location is None or for_location == self._location:
			self._insert_rows(rows)
			self._check_no_duplicate_rows()
	def _on_location_loaded(self, location):
		assert is_in_main_thread()
		if location == self._location:
			self._file_watcher.watch(location)
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
		assert is_in_main_thread()
		if self._is_in_root(row.url):
			self._on_rows_loaded([row])
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
				self._on_rows_loaded([row])
		else:
			if is_in_root:
				self._update_rows([row], rownum)
				self._check_no_duplicate_rows()
			else:
				self._remove_rows(rownum)
	@run_in_main_thread
	def _on_file_removed(self, url):
		try:
			rownum = self.find(url).row()
		except ValueError:
			pass
		else:
			self._remove_rows(rownum)
	def _on_file_changed(self, url):
		assert is_in_main_thread()
		if url == self._location:
			# The common case
			self.reload(url)
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
			self._update_rows([row], index.row())
			self._check_no_duplicate_rows()
	def _insert_rows(self, rows, first_rownum=-1):
		if first_rownum == -1:
			first_rownum = len(self._rows)
		# Consider: The user creates C:\foo.txt. We are notified of this twice:
		#  1) _on_file_added("C:\foo.txt")
		#  2) _on_file_changed("C:\")
		# Both of these call _insert_rows(...). However, we do not know which
		# one will be called first. Because of this, we need to check in both
		# cases whether the file has already been added. The easiest place to do
		# this is here:
		to_insert = self._get_rows_to_insert(rows)
		if not to_insert:
			return
		self.beginInsertRows(
			QModelIndex(), first_rownum, first_rownum + len(to_insert) - 1
		)
		self._rows = \
			self._rows[:first_rownum] + to_insert + self._rows[first_rownum:]
		self.endInsertRows()
	def _check_no_duplicate_rows(self):
		assert len({r.url for r in self._rows}) == len(self._rows), \
			"Invariant violated: Duplicate rows."
	def _get_rows_to_insert(self, rows):
		result = []
		for row in rows:
			try:
				self.find(row.url)
			except ValueError:
				result.append(row)
		return result
	def _update_rows(self, rows, first_rownum):
		self._rows[first_rownum : first_rownum + len(rows)] = rows
		top_left = self.index(first_rownum, 0)
		bottom_right = \
			self.index(first_rownum + len(rows) - 1, self.columnCount() - 1)
		self.dataChanged.emit(top_left, bottom_right)
	def _remove_rows(self, start, end=-1):
		if end == -1:
			end = start + 1
		self.beginRemoveRows(QModelIndex(), start, end - 1)
		del self._rows[start:end]
		self.endRemoveRows()
	def _move_rows(self, cut_start, cut_end, insert_start):
		dst_row = self._get_move_destination(cut_start, cut_end, insert_start)
		assert self.beginMoveRows(
			QModelIndex(), cut_start, cut_end - 1, QModelIndex(), dst_row
		)
		rows = self._rows[cut_start:cut_end]
		self._rows = self._rows[:cut_start] + self._rows[cut_end:]
		self._rows = \
			self._rows[:insert_start] + rows + self._rows[insert_start:]
		self.endMoveRows()
	@classmethod
	def _get_move_destination(cls, cut_start, cut_end, insert_start):
		if cut_start == insert_start:
			raise ValueError(
				'Not a move operation (%d, %d)' % (cut_start, cut_end)
			)
		num_rows = cut_end - cut_start
		return insert_start + (num_rows if cut_start < insert_start else 0)
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
		try:
			# It is tempting to simply do `future.result()` here without
			# try...except. But this crashes the thread for Python's
			# ThreadPoolExecutor and results in it logging
			# "CRITICAL:concurrent.futures:Exception in worker".
			# So instead, we catch exceptions and forward them to
			# sys.excepthook(...).
			future.result()
		except (Exception, SystemExit):
			sys.excepthook(*sys.exc_info())
	def _is_in_root(self, url):
		return dirname(url) == self._location

class FileWatcher:
	"""
	Say we're at ~/Downloads and the user presses Backspace to go up to ~.
	Here's what typically happens:
	 1) we "unwatch" ~/Downloads
	 2) we load and display the files in ~
	 3) we "watch" ~.

	Now consider what happens if the user presses Backspace *before* ~/Downloads
	was fully loaded, ie. we're still at step 2) above. In this case, we are
	not yet "watching" ~/Downloads but are already executing step 1), which is
	to "unwatch" it. This produces an error.

	The purpose of this helper class is to solve the above problem. It remembers
	which paths are actually being watched and offers a #clear() method that
	unwatches precisely those paths. This way, only paths that were actually
	watched are ever "unwatched".
	"""
	def __init__(self, fs, callback):
		self._fs = fs
		self._callback = callback
		self._watched_files = []
	def watch(self, url):
		self._fs.add_file_changed_callback(url, self._callback)
		self._watched_files.append(url)
	def clear(self):
		for url in self._watched_files:
			self._fs.remove_file_changed_callback(url, self._callback)
		self._watched_files = []

class SortedFileSystemModel(QSortFilterProxyModel):
	def __init__(self, parent, fs, null_location):
		super().__init__(parent)
		self._fs = fs
		self._null_location = null_location
		self._filters = []
		self.setSourceModel(FileSystemModel(fs, null_location))
		self._fs.file_removed.add_callback(self._on_file_removed)
	def set_location(self, url, callback=None):
		self.sourceModel().set_location(url, callback)
	def get_location(self):
		return self.sourceModel().get_location()
	def get_columns(self):
		return self.sourceModel().get_columns()
	def reload(self):
		self.sourceModel().reload()
	def lessThan(self, left, right):
		source = self.sourceModel()
		column = self.sortColumn()
		is_ascending = self.sortOrder() == AscendingOrder
		def get_sort_value(l_r):
			return source.get_sort_value(l_r.row(), column, is_ascending)
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
	@property
	def file_renamed(self):
		return self.sourceModel().file_renamed
	@property
	def files_dropped(self):
		return self.sourceModel().files_dropped
	@property
	def location_changed(self):
		return self.sourceModel().location_changed
	@property
	def location_loaded(self):
		return self.sourceModel().location_loaded
	def url(self, index):
		return self.sourceModel().url(self.mapToSource(index))
	def find(self, url):
		return self.mapFromSource(self.sourceModel().find(url))
	@run_in_main_thread
	def _on_file_removed(self, url):
		if is_pardir(url, self.get_location()):
			existing_pardir = get_existing_pardir(url, self._fs.is_dir)
			self.set_location(existing_pardir or self._null_location)