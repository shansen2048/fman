from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor
from fman.impl.model.diff import ComputeDiff
from fman.impl.model.fs import NameColumn, SizeColumn, LastModifiedColumn
from fman.url import dirname, join
from fman.util import is_debug, EqMixin, ReprMixin, ConstructorMixin
from fman.util.qt import ItemIsEnabled, ItemIsEditable, ItemIsSelectable, \
	EditRole, AscendingOrder, DisplayRole, ItemIsDragEnabled, \
	ItemIsDropEnabled, CopyAction, MoveAction, IgnoreAction, DecorationRole, \
	run_in_main_thread, is_in_main_thread
from PyQt5.QtCore import pyqtSignal, QSortFilterProxyModel, QVariant, QUrl, \
	QMimeData, QAbstractTableModel, QModelIndex, Qt

import sip
import sys

class DragAndDropMixin(QAbstractTableModel):

	files_dropped = pyqtSignal(list, str, bool)

	def supportedDropActions(self):
		return MoveAction | CopyAction | IgnoreAction
	def canDropMimeData(self, data, action, row, column, parent):
		if not action & self.supportedDropActions():
			return False
		if not data.hasUrls():
			return False
		dest_dir = self._get_drop_dest(parent)
		is_in_dest_dir = lambda url: dirname(url.toString()) == dest_dir
		return not all(map(is_in_dest_dir, data.urls()))
	def mimeTypes(self):
		"""
		List the MIME types used by our drag and drop implementation.
		"""
		return ['text/uri-list']
	def mimeData(self, indexes):
		result = QMimeData()
		result.setUrls([QUrl(self.url(index)) for index in indexes])
		# The Qt documentation (http://doc.qt.io/qt-5/dnd.html) states that the
		# QMimeData should not be deleted, because the target of the drag and
		# drop operation takes ownership of it. We must therefore tell SIP not
		# to garbage-collect `result` once this method returns. Without this
		# instruction, we get a horrible crash because Qt tries to access an
		# object that has already been gc'ed:
		sip.transferto(result, None)
		return result
	def dropMimeData(self, data, action, row, column, parent):
		if action == IgnoreAction:
			return True
		if not data.hasUrls():
			return False
		urls = [url.toString() for url in data.urls()]
		dest = self._get_drop_dest(parent)
		if action in (MoveAction, CopyAction):
			self.files_dropped.emit(urls, dest, action == CopyAction)
			return True
		return False
	def _get_drop_dest(self, index):
		return self.url(index) if index.isValid() else self.location()

class PreloadedRow(ConstructorMixin, EqMixin, ReprMixin):
	"""
	The sole purpose of this subclass is to compare icons by their `.cacheKey()`
	rather than directly (which always returns False, except for self == self).
	"""

	_FIELDS = ('url', 'is_dir', 'icon', 'columns')

	def _get_field_values(self):
		return (self.url, self.is_dir, self.icon.cacheKey(), self.columns)

PreloadedColumn = \
	namedtuple('PreloadedColumn', ('str', 'sort_value_asc', 'sort_value_desc'))

class FileSystemModel(DragAndDropMixin):

	file_renamed = pyqtSignal(str, str)
	location_changed = pyqtSignal(str)
	directory_loaded = pyqtSignal(str)

	def __init__(self, fs):
		super().__init__()
		self._fs = fs
		self._location = ''
		self._rows = []
		self._executor = ThreadPoolExecutor()
		self._columns = (NameColumn(), SizeColumn(), LastModifiedColumn())
		self._file_watcher = FileWatcher(fs, self._on_file_changed)
		self._connect_signals()
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
		self.directory_loaded.connect(self._on_directory_loaded)
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
		return QVariant()
	def headerData(self, section, orientation, role=DisplayRole):
		if orientation == Qt.Horizontal and role == DisplayRole \
			and 0 <= section < self.columnCount():
			return QVariant(self._columns[section].name)
		return QVariant()
	def location(self):
		return self._location
	def set_location(self, url, callback):
		url = self._fs.resolve(url)
		if url == self._location:
			callback(url)
		else:
			self._file_watcher.clear()
			self._location = url
			self.location_changed.emit(url)
			self.beginResetModel()
			self._rows = []
			self.endResetModel()
			self._execute_async(self._load_rows, url, callback)
		return QModelIndex()
	def url(self, index):
		if not self._index_is_valid(index):
			raise ValueError("Invalid index")
		return self._rows[index.row()].url
	def index(self, *args):
		if len(args) == 2:
			rownum, column = args
			parent = QModelIndex()
		else:
			rownum, column, parent = args
		return super().index(rownum, column, parent)
	def find(self, url):
		if url == self._location:
			return QModelIndex()
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
	def reload(self, location):
		# TODO: Don't allow reload when initial load is still in progress.
		assert not is_in_main_thread()
		# Abort reload if path changed:
		if location != self._location:
			return
		self._fs.clear_cache(location)
		rows = []
		for file_name in self._fs.iterdir(location):
			file_url = join(location, file_name)
			self._fs.clear_cache(file_url)
			rows.append(self._load_row(file_url))
			# Abort reload if path changed:
			if location != self._location:
				return
		self._on_reloaded(location, rows)
	@run_in_main_thread
	def _on_reloaded(self, location, rows):
		# Abort reload if path changed:
		if location != self._location:
			return
		diff = ComputeDiff(self._rows, rows)()
		for entry in diff:
			if entry.type == 'change':
				self._update_rows(entry.rows, entry.insert_start)
			elif entry.type == 'remove':
				self._remove_rows(entry.cut_start, entry.cut_end)
			elif entry.type == 'insert':
				self._insert_rows(entry.rows, entry.insert_start)
			elif entry.type == 'move':
				self._move_rows(
					entry.cut_start, entry.insert_start, len(entry.rows)
				)
			elif entry.type == 'other':
				self._remove_rows(entry.cut_start, entry.cut_end)
				self._insert_rows(entry.rows, entry.insert_start)
			else:
				raise NotImplementedError(entry.type)
		if is_debug():
			assert rows == self._rows, '%r != %r' % (rows, self._rows)
	def get_sort_value(self, row, column, is_ascending):
		col = self._rows[row].columns[column]
		return col.sort_value_asc if is_ascending else col.sort_value_desc
	def _index_is_valid(self, index):
		if not index.isValid() or index.model() != self:
			return False
		return 0 <= index.row() < self.rowCount() and \
			   0 <= index.column() < self.columnCount()
	def _load_rows(self, location, callback):
		assert not is_in_main_thread()
		if location != self._location:
			# Root path changed since this method was scheduled. Abort.
			return
		for file_name in self._fs.iterdir(location):
			file_url = join(location, file_name)
			row = self._load_row(file_url)
			self._on_row_loaded(row, location)
			if location != self._location:
				# Root path changed. Abort.
				return
		callback(location)
		self.directory_loaded.emit(location)
	def _load_row(self, url):
		return PreloadedRow(
			url, self._fs.is_dir(url), self._fs.icon(url),
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
	def _on_row_loaded(self, row, for_location=None):
		if for_location is None or for_location == self._location:
			self._insert_rows([row])
	def _on_directory_loaded(self, location):
		assert is_in_main_thread()
		if location == self._location:
			self._file_watcher.watch(location)
	def _on_file_added(self, url):
		assert not is_in_main_thread()
		if self._is_in_root(url):
			row = self._load_row(url)
			self._on_row_loaded_for_add(row)
	@run_in_main_thread
	def _on_row_loaded_for_add(self, row):
		assert is_in_main_thread()
		if self._is_in_root(row.url):
			self._on_row_loaded(row)
	def _on_file_moved(self, old_url, new_url):
		assert not is_in_main_thread()
		if not self._is_in_root(old_url) and not self._is_in_root(new_url):
			return
		row = self._load_row(new_url)
		self._on_row_loaded_for_move(row, old_url)
	@run_in_main_thread
	def _on_row_loaded_for_move(self, row, old_url):
		# We don't just remove the old row and add the new one because this
		# destroys the cursor state.
		try:
			rownum = self.find(old_url).row()
		except ValueError:
			if self._is_in_root(row.url):
				self._on_row_loaded(row)
		else:
			if self._is_in_root(row.url):
				self._update_rows([row], rownum)
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
			self._execute_async(self.reload, url)
		elif self._is_in_root(url):
			self._execute_async(self._reload_row, url)
	def _reload_row(self, url):
		assert not is_in_main_thread()
		if self._is_in_root(url): # Root could have changed in the meantime
			row = self._load_row(url)
			self._on_row_loaded_for_reload(row)
	@run_in_main_thread
	def _on_row_loaded_for_reload(self, row):
		try:
			index = self.find(row.url)
		except ValueError:
			pass
		else:
			self._update_rows([row], index.row())
	def _insert_rows(self, rows, first_rownum=-1):
		if first_rownum == -1:
			first_rownum = len(self._rows)
		self.beginInsertRows(
			QModelIndex(), first_rownum, first_rownum + len(rows) - 1
		)
		self._rows = \
			self._rows[:first_rownum] + rows + self._rows[first_rownum:]
		self.endInsertRows()
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
	def _move_rows(self, cut_start, insert_start, num_rows):
		destination_row = \
			self._get_move_destination(cut_start, insert_start, num_rows)
		assert self.beginMoveRows(
			QModelIndex(), cut_start, cut_start + num_rows - 1,
			QModelIndex(), destination_row
		)
		rows = self._rows[cut_start:cut_start + num_rows]
		self._rows = self._rows[:cut_start] + self._rows[cut_start + num_rows:]
		self._rows = \
			self._rows[:insert_start] + rows + self._rows[insert_start:]
		self.endMoveRows()
	@classmethod
	def _get_move_destination(cls, cut_start, insert_start, num_rows):
		if cut_start == insert_start:
			raise ValueError(
				'Not a move operation (%d, %d)' % (cut_start, num_rows)
			)
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
			future.result()
		except:
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

class SortDirectoriesBeforeFiles(QSortFilterProxyModel):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.filters = []
	def set_location(self, url, callback):
		source_index = self.sourceModel().set_location(url, callback)
		# We filter out hidden files/dirs below the current root path.
		# Consider the following: We're at ~ and change to a hidden subfolder,
		# ~/Library. We previously filtered out ~/Library because it is hidden.
		# Now however, we do want to include it (because we want to see its
		# contents). The problem is that the source model doesn't notify us
		# of the call to setRootPath(...) above. When we're queried for
		# ~/Library, the base implementation in QSortFilterProxyModel thus
		# returns the cached result, which is "don't include".
		# We use the following call to notify the base implementation that the
		# filter needs to be recomputed for the new root path:
		self.sourceModel().dataChanged.emit(source_index, source_index, [])
		return self.mapFromSource(source_index)
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
		for filter_ in self.filters:
			if not filter_(url):
				return False
		return True
	def add_filter(self, filter_):
		self.filters.append(filter_)