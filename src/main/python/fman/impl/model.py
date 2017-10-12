from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from fman.impl.trash import move_to_trash
from fman.util import listdir_absolute, Signal, is_debug, EqMixin, ReprMixin, \
	ConstructorMixin
from fman.util.qt import ItemIsEnabled, ItemIsEditable, ItemIsSelectable, \
	EditRole, AscendingOrder, DisplayRole, ItemIsDragEnabled, \
	ItemIsDropEnabled, CopyAction, MoveAction, IgnoreAction, DecorationRole
from functools import lru_cache
from math import log
from os import rename, remove
from os.path import commonprefix, isdir, dirname, normpath, basename, \
	getmtime, getsize
from pathlib import Path
from PyQt5.QtCore import pyqtSignal, QSortFilterProxyModel, QFileInfo, \
	QVariant, QUrl, QMimeData, QAbstractTableModel, QModelIndex, Qt, QObject, \
	QThread, QFileSystemWatcher
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QFileIconProvider
from shutil import rmtree
from threading import Lock
from weakref import WeakValueDictionary

import logging
import sip
import sys

_LOG = logging.getLogger(__name__)

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
		is_in_dest_dir = lambda url: dirname(url.toLocalFile()) == dest_dir
		return not all(map(is_in_dest_dir, data.urls()))
	def mimeTypes(self):
		"""
		List the MIME types used by our drag and drop implementation.
		"""
		return ['text/uri-list']
	def mimeData(self, indexes):
		result = QMimeData()
		result.setUrls([
			QUrl.fromLocalFile(self.filePath(index))
			for index in indexes
		])
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
		# On OS X, url.toLocalFile() ends in '/' for directories. Get rid of
		# this via normpath(...):
		urls = [normpath(url.toLocalFile()) for url in data.urls()]
		dest = self._get_drop_dest(parent)
		if action in (MoveAction, CopyAction):
			self.files_dropped.emit(urls, dest, action == CopyAction)
			return True
		return False
	def _get_drop_dest(self, index):
		return self.filePath(index) if index.isValid() else self.rootPath()

class PreloadedRow(ConstructorMixin, EqMixin, ReprMixin):
	"""
	The sole purpose of this subclass is to compare icons by their `.cacheKey()`
	rather than directly (which always returns False, except for self == self).
	"""

	_FIELDS = ('path', 'isdir', 'icon', 'columns')

	def _get_field_values(self):
		return (
			self.path, self.isdir,
			self.icon.cacheKey() if self.icon else None,
			self.columns
		)

PreloadedColumn = \
	namedtuple('PreloadedColumn', ('str', 'sort_value_asc', 'sort_value_desc'))

class FileSystemModel(DragAndDropMixin):

	file_renamed = pyqtSignal(str, str)
	rootPathChanged = pyqtSignal(str)
	directoryLoaded = pyqtSignal(str)

	# These signals are used for communication across threads:
	_row_loaded = pyqtSignal(PreloadedRow)
	_row_loaded_for_add = pyqtSignal(PreloadedRow)
	_row_loaded_for_rename = pyqtSignal(PreloadedRow, str)
	_row_loaded_for_reload = pyqtSignal(PreloadedRow)
	_reloaded = pyqtSignal(str, list)

	def __init__(self, fs, parent=None):
		super().__init__(parent)
		self._fs = fs
		self._root_path = ''
		self._rows = []
		self._executor = ThreadPoolExecutor()
		self._columns = (
			NameColumn(self._fs), SizeColumn(self._fs),
			LastModifiedColumn(self._fs)
		)
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

		To accommodate the above, we connect to file system signals via blocking
		connections (Direct- or BlockingQueuedConnection). On the other hand,
		the thread safety of this class works by only performing changing
		operations in its QObject#thread(). To synchronize the two ends, we use
		signals ([*] below) to communicate between the different threads.
		"""
		self._fs.file_added.connect(self._on_file_added, Qt.DirectConnection)
		self._fs.file_renamed.connect(
			self._on_file_renamed, Qt.DirectConnection
		)
		self._fs.file_removed.connect(
			self._on_file_removed, Qt.BlockingQueuedConnection
		)
		self._fs.file_changed.connect(self._on_file_changed)

		# [*]: These are the signals that are used to communicate with threads:
		self._row_loaded.connect(self._on_row_loaded)
		self._row_loaded_for_add.connect(
			self._on_row_loaded, Qt.BlockingQueuedConnection
		)
		self._row_loaded_for_rename.connect(
			self._on_row_loaded_for_rename, Qt.BlockingQueuedConnection
		)
		self._row_loaded_for_reload.connect(
			self._on_row_loaded_for_reload, Qt.BlockingQueuedConnection
		)
		self._reloaded.connect(self._on_reloaded, Qt.BlockingQueuedConnection)
		self.directoryLoaded.connect(self._fs.watch)
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
				icon = self._rows[index.row()].icon
				if icon:
					return icon
		return QVariant()
	def headerData(self, section, orientation, role=DisplayRole):
		if orientation == Qt.Horizontal and role == DisplayRole \
			and 0 <= section < self.columnCount():
			return QVariant(self._columns[section].name)
		return QVariant()
	def rootPath(self):
		return self._root_path
	def myComputer(self):
		return ''
	def setRootPath(self, path):
		if path != self._root_path:
			if self._root_path:
				self._fs.unwatch(self._root_path)
			self._root_path = path
			self.rootPathChanged.emit(path)
			self.beginResetModel()
			self._rows = []
			self.endResetModel()
			self._executor.submit(self._load_rows, path)
		return QModelIndex()
	def filePath(self, index):
		if not self._index_is_valid(index):
			raise ValueError("Invalid index")
		return self._rows[index.row()].path
	def index(self, *args):
		if len(args) == 1:
			file_path = args[0]
			if file_path == self._root_path:
				return QModelIndex()
			for rownum, row in enumerate(self._rows):
				if row.path == file_path:
					break
			else:
				raise ValueError('%r is not in list' % file_path)
			column = 0
			parent = QModelIndex()
		elif len(args) == 2:
			rownum, column = args
			parent = QModelIndex()
		else:
			rownum, column, parent = args
		return super().index(rownum, column, parent)
	def flags(self, index):
		if index == QModelIndex():
			# The "root path":
			return ItemIsDropEnabled
		# Need to set ItemIsEnabled - in particular for the last column - to
		# make keyboard shortcut "End" work. When we press this shortcut in a
		# QTableView, Qt jumps to the last column of the last row. But only if
		# this cell is enabled. If it isn't enabled, Qt simply does nothing.
		# So we set the cell to enabled.
		result = ItemIsSelectable | ItemIsEnabled
		if index.column() == 0:
			result |= ItemIsEditable | ItemIsDragEnabled
			if self._rows[index.row()].isdir:
				result |= ItemIsDropEnabled
		return result
	def setData(self, index, value, role):
		if role == EditRole:
			self.file_renamed.emit(self.filePath(index), value)
			return True
		return super().setData(index, value, role)
	def reload(self, path):
		# TODO: Don't allow reload when initial load is still in progress.
		assert not self._is_in_home_thread()
		self._fs.clear_cache(path)
		rows = []
		for file_path in self._fs.listdir(path):
			self._fs.clear_cache(file_path)
			rows.append(self._load_row(file_path))
		self._reloaded.emit(path, rows)
	def _on_reloaded(self, path, rows):
		assert self._is_in_home_thread()
		if path != self._root_path:
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
	def _load_rows(self, path):
		assert not self._is_in_home_thread()
		for file_path in self._fs.listdir(path):
			self._row_loaded.emit(self._load_row(file_path))
		self.directoryLoaded.emit(path)
	def _load_row(self, path):
		return PreloadedRow(
			path, self._fs.isdir(path), self._fs.icon(path),
			[
				PreloadedColumn(
					QVariant(column.get_str(path)),
					column.get_sort_value(path, True),
					column.get_sort_value(path, False)
				)
				for column in self._columns
			]
		)
	def _on_row_loaded(self, row):
		assert self._is_in_home_thread()
		if not self._is_in_root(row.path):
			return
		self._insert_rows([row])
	def _on_file_added(self, path):
		assert not self._is_in_home_thread()
		row = self._load_row(path)
		self._row_loaded_for_add.emit(row)
	def _on_file_renamed(self, old_path, new_path):
		assert not self._is_in_home_thread()
		row = self._load_row(new_path)
		self._row_loaded_for_rename.emit(row, old_path)
	def _on_row_loaded_for_rename(self, row, old_path):
		assert self._is_in_home_thread()
		# We don't just remove the old row and add the new one because this
		# destroys the cursor state.
		try:
			rownum = self.index(old_path).row()
		except ValueError:
			self._on_row_loaded(row)
		else:
			assert self._is_in_root(old_path)
			if self._is_in_root(row.path):
				self._update_rows([row], rownum)
			else:
				self._remove_rows(rownum)
	def _on_file_removed(self, file_path):
		assert self._is_in_home_thread()
		try:
			row = self.index(file_path).row()
		except ValueError:
			pass
		else:
			self._remove_rows(row)
	def _on_file_changed(self, path):
		assert self._is_in_home_thread()
		if path == self._root_path:
			# The common case
			self._executor.submit(self.reload, path)
		else:
			if self._is_in_root(path):
				self._executor.submit(self._reload_row, path)
	def _reload_row(self, path):
		assert not self._is_in_home_thread()
		row = self._load_row(path)
		self._row_loaded_for_reload.emit(row)
	def _on_row_loaded_for_reload(self, row):
		assert self._is_in_home_thread()
		try:
			index = self.index(row.path)
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
	def _is_in_root(self, path):
		return dirname(path) == self._root_path
	def _is_in_home_thread(self):
		return QThread.currentThread() == self.thread()

class ComputeDiff:
	"""
	N.B.: This implementation requires that there be no duplicate rows!
	"""
	def __init__(self, old_rows, new_rows):
		self._old_rows = list(old_rows)
		self._new_rows = new_rows
		self._result = []
	def __call__(self):
		for i in range(len(self._old_rows)-1, -1, -1):
			if self._old_rows[i] not in self._new_rows:
				self._remove_row(i)
		for i, new_row in enumerate(self._new_rows):
			if new_row not in self._old_rows:
				self._insert_row(i, new_row)
		for i, new_row in enumerate(self._new_rows):
			if new_row != self._old_rows[i]:
				self._move_row(self._old_rows.index(new_row, i), i)
		assert self._old_rows == self._new_rows
		return self._join_adjacent()
	def _remove_row(self, i):
		self._result.append(DiffEntry(i, i + 1, 0, []))
		self._old_rows.pop(i)
	def _insert_row(self, i, row):
		self._result.append(DiffEntry(0, 0, i, [row]))
		self._old_rows.insert(i, row)
	def _move_row(self, src, dest):
		row = self._old_rows.pop(src)
		self._old_rows.insert(dest, row)
		self._result.append(DiffEntry(src, src + 1, dest, [row]))
	def _join_adjacent(self):
		if not self._result:
			return []
		result = [self._result[0]]
		for entry in self._result[1:]:
			if not result[-1].extend_by(entry):
				result.append(entry)
		return result

class DiffEntry(ConstructorMixin, EqMixin, ReprMixin):

	_FIELDS = ('cut_start', 'cut_end', 'insert_start', 'rows')

	def extend_by(self, other):
		if not self.rows and other.cut_start == self.cut_end:
			self.cut_end = other.cut_end
			self.rows = other.rows
			return True
		if not other.rows and other.cut_end == self.cut_start:
			self.cut_start = other.cut_start
			return True
		if not other.does_cut and other.insert_start == self.insert_end:
			self.rows += other.rows
			return True
		return False
	@property
	def type(self):
		if not self.does_cut:
			assert self.rows
			return 'insert'
		if self.rows:
			if self.cut_end - self.cut_start == len(self.rows):
				if self.cut_start == self.insert_start:
					return 'change'
				else:
					return 'move'
			return 'other'
		else:
			return 'remove'
	@property
	def does_cut(self):
		return self.cut_end > self.cut_start
	@property
	def insert_end(self):
		return self.insert_start + len(self.rows)

class FileSystem:
	def __init__(self):
		self.file_changed = Signal()
	def broadcast_file_changed(self, path):
		self.file_changed.emit(path)

class DefaultFileSystem(FileSystem):
	def __init__(self, icon_provider=None):
		super().__init__()
		self._icon_provider = icon_provider
		self._watcher = QFileSystemWatcher()
		self._watcher.directoryChanged.connect(self.broadcast_file_changed)
		self._watcher.fileChanged.connect(self.broadcast_file_changed)
	def exists(self, path):
		return Path(path).exists()
	def listdir(self, path):
		return listdir_absolute(path)
	def isdir(self, path):
		return isdir(path)
	def getsize(self, path):
		return getsize(path)
	def getmtime(self, path):
		return getmtime(path)
	def icon(self, path):
		if self._icon_provider:
			return self._icon_provider.icon(QFileInfo(path))
	def touch(self, path):
		Path(path).touch()
	def mkdir(self, path):
		Path(path).mkdir()
	def rename(self, old_path, new_path):
		rename(old_path, new_path)
	def move_to_trash(self, file_path):
		move_to_trash(file_path)
	def delete(self, path):
		if self.isdir(path):
			rmtree(path)
		else:
			remove(path)
	def watch(self, path):
		self._watcher.addPath(path)
	def unwatch(self, path):
		self._watcher.removePath(path)

class CachedFileSystem(QObject):

	file_renamed = pyqtSignal(str, str)
	file_removed = pyqtSignal(str)
	file_added = pyqtSignal(str)
	file_changed = pyqtSignal(str)

	def __init__(self, source):
		super().__init__()
		self._source = source
		self._cache = {}
		self._cache_locks = WeakValueDictionary()
		source.file_changed.connect(self._on_source_file_changed)
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
		return self._query_cache(path, 'icon', self._source.icon)
	def touch(self, path):
		self._source.touch(path)
		if path not in self._cache:
			self._add_to_parent(path)
			self.file_added.emit(path)
	def mkdir(self, path):
		self._source.mkdir(path)
		if path not in self._cache:
			self._add_to_parent(path)
			self.file_added.emit(path)
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
		self.file_renamed.emit(old_path, new_path)
	def move_to_trash(self, path):
		self._source.move_to_trash(path)
		self._remove(path)
		self.file_removed.emit(path)
	def delete(self, path):
		self._source.delete(path)
		self._remove(path)
		self.file_removed.emit(path)
	def watch(self, path):
		self._source.watch(path)
	def unwatch(self, path):
		self._source.unwatch(path)
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
		self.file_changed.emit(path)

class SortDirectoriesBeforeFiles(QSortFilterProxyModel):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.filters = []
	def setRootPath(self, path):
		source_index = self.sourceModel().setRootPath(path)
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
		file_path = source.filePath(source.index(source_row, 0, source_parent))
		# When rootPath() is /Users, Qt calls filterAcceptsRow(...) with
		# '/' and '/Users' before the actual contents of /Users. If we return
		# False for any of these parent directories, then Qt doesn't display any
		# entries in a subdirectory. So make sure we return True:
		is_pardir = file_path == commonprefix([file_path, source.rootPath()])
		if is_pardir:
			return True
		for filter_ in self.filters:
			if not filter_(file_path):
				return False
		return True
	def add_filter(self, filter_):
		self.filters.append(filter_)

class Column:
	def __init__(self, fs):
		self.fs = fs
	def get_str(cls, file_path):
		raise NotImplementedError()
	def get_sort_value(self, file_path, is_ascending):
		"""
		This method should generally be independent of is_ascending.
		When is_ascending is False, Qt simply reverses the sort order.
		However, we may sometimes want to change the sort order in a way other
		than a simple reversal when is_ascending is False. That's why this
		method receives is_ascending as a parameter.
		"""
		raise NotImplementedError()

class NameColumn(Column):

	name = 'Name'

	def get_str(self, file_path):
		return basename(file_path)
	def get_sort_value(self, file_path, is_ascending):
		is_dir = self.fs.isdir(file_path)
		return is_dir ^ is_ascending, basename(file_path).lower()

class SizeColumn(Column):

	name = 'Size'

	def get_str(self, file_path):
		if self.fs.isdir(file_path):
			return ''
		size_bytes = self.fs.getsize(file_path)
		units = ('%d bytes', '%d KB', '%.1f MB', '%.1f GB')
		if size_bytes <= 0:
			unit_index = 0
		else:
			unit_index = min(int(log(size_bytes, 1024)), len(units) - 1)
		unit = units[unit_index]
		base = 1024 ** unit_index
		return unit % (size_bytes / base)
	def get_sort_value(self, file_path, is_ascending):
		is_dir = self.fs.isdir(file_path)
		if is_dir:
			ord_ = ord if is_ascending else lambda c: -ord(c)
			minor = tuple(ord_(c) for c in basename(file_path).lower())
		else:
			minor = self.fs.getsize(file_path)
		return is_dir ^ is_ascending, minor

class LastModifiedColumn(Column):

	name = 'Modified'

	def get_str(self, file_path):
		try:
			modified = datetime.fromtimestamp(self.fs.getmtime(file_path))
		except OSError:
			return ''
		return modified.strftime('%Y-%m-%d %H:%M')
	def get_sort_value(self, file_path, is_ascending):
		is_dir = self.fs.isdir(file_path)
		return is_dir ^ is_ascending, self.fs.getmtime(file_path)

class GnomeFileIconProvider(QFileIconProvider):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		try:
			self.Gtk, self.Gio = self._init_pgi()
		except (ImportError, ValueError) as e:
			raise GnomeNotAvailable() from e
	def _init_pgi(self):
		import pgi
		pgi.install_as_gi()
		import gi
		gi.require_version('Gtk', '3.0')
		try:
			from gi.repository import Gtk, Gio
		except AttributeError as e:
			if e.args == (
				"'GLib' module has not attribute 'uri_list_extract_uris'",
			):
				# This happens when we run fman from source.
				sys.modules['pgi.overrides.GObject'] = None
				from gi.repository import Gtk, Gio
		# This is required when we use pgi in a PyInstaller-frozen app. See:
		# https://github.com/lazka/pgi/issues/38
		Gtk.init(sys.argv)
		return Gtk, Gio
	def icon(self, arg):
		result = None
		if isinstance(arg, QFileInfo):
			result = self._icon(arg.absoluteFilePath())
		return result or super().icon(arg)
	def _icon(self, file_path):
		gio_file = self.Gio.file_new_for_path(file_path)
		nofollow_symlinks = self.Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS
		try:
			file_info = gio_file.query_info(
				'standard::icon', nofollow_symlinks, None
			)
		except Exception:
			_LOG.exception("Could not obtain icon for %s", file_path)
		else:
			if file_info:
				icon = file_info.get_icon()
				if icon:
					icon_names = icon.get_names()
					if icon_names:
						return self._load_gtk_icon(icon_names[0])
	@lru_cache()
	def _load_gtk_icon(self, name, size=32):
		theme = self.Gtk.IconTheme.get_default()
		if theme:
			icon = theme.lookup_icon(name, size, 0)
			if icon:
				return QIcon(icon.get_filename())

class GnomeNotAvailable(RuntimeError):
	pass