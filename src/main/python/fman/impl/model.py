from datetime import datetime
from fman.impl.trash import move_to_trash
from fman.util import listdir_absolute
from fman.util.qt import ItemIsEnabled, ItemIsEditable, ItemIsSelectable, \
	EditRole, AscendingOrder, DisplayRole, ItemIsDragEnabled, \
	ItemIsDropEnabled, CopyAction, MoveAction, IgnoreAction, DecorationRole
from functools import lru_cache
from math import log
from os import rename
from os.path import commonprefix, isdir, dirname, normpath, basename, \
	getmtime, getsize
from PyQt5.QtCore import pyqtSignal, QSortFilterProxyModel, QFileInfo, \
	QVariant, QUrl, QMimeData, QAbstractTableModel, QModelIndex, Qt, QObject
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QFileIconProvider

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

class FileSystemModel(DragAndDropMixin):

	file_renamed = pyqtSignal(str, str)
	rootPathChanged = pyqtSignal(str)
	directoryLoaded = pyqtSignal(str)

	def __init__(self, fs, icon_provider=None, parent=None):
		super().__init__(parent)
		self._icon_provider = icon_provider
		self._root_path = ''
		self._items = []
		self._fs = fs
		self.columns = (
			NameColumn(self._fs), SizeColumn(self._fs),
			LastModifiedColumn(self._fs)
		)
		self._fs.file_renamed.connect(self._on_file_renamed)
		self._fs.file_removed.connect(self._on_file_removed)
	def rowCount(self, parent=QModelIndex()):
		if parent.isValid():
			# According to the Qt docs for QAbstractItemModel#rowCount(...):
			# "When implementing a table based model, columnCount() should
			#  return 0 when the parent is valid."
			return 0
		return len(self._items)
	def columnCount(self, parent=QModelIndex()):
		if parent.isValid():
			# According to the Qt docs for QAbstractItemModel#columnCount(...):
			# "When implementing a table based model, columnCount() should
			#  return 0 when the parent is valid."
			return 0
		return len(self.columns)
	def data(self, index, role=DisplayRole):
		if self._index_is_valid(index):
			if role in (DisplayRole, EditRole):
				file_path = self._items[index.row()]
				column = self.columns[index.column()]
				try:
					return QVariant(column.get_str(file_path))
				except FileNotFoundError:
					# We don't remove the file from `self._items` here because
					# we rely on the FS implementation to tell us that the file
					# has been removed.
					return QVariant()
			elif role == DecorationRole:
				if self._icon_provider and index.column() == 0:
					file_info = QFileInfo(self.filePath(index))
					return self._icon_provider.icon(file_info)
		return QVariant()
	def headerData(self, section, orientation, role=DisplayRole):
		if orientation == Qt.Horizontal and role == DisplayRole \
			and 0 <= section < self.columnCount():
			return QVariant(self.columns[section].name)
		return QVariant()
	def rootPath(self):
		return self._root_path
	def myComputer(self):
		return ''
	def setRootPath(self, path):
		if path != self._root_path:
			self._root_path = path
			self.rootPathChanged.emit(path)
			self.beginResetModel()
			self._items = self._fs.listdir(path)
			self.endResetModel()
			self.directoryLoaded.emit(path)
		return QModelIndex()
	def filePath(self, index):
		if not self._index_is_valid(index):
			raise ValueError("Invalid index")
		return self._items[index.row()]
	def index(self, *args):
		try:
			row, column, parent = args
		except ValueError:
			file_path, = args
			if file_path == self._root_path:
				return QModelIndex()
			row = self._items.index(file_path)
			column = 0
			parent = QModelIndex()
		return super().index(row, column, parent)
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
			if self._fs.isdir(self.filePath(index)):
				result |= ItemIsDropEnabled
		return result
	def setData(self, index, value, role):
		if role == EditRole:
			self.file_renamed.emit(self.filePath(index), value)
			return True
		return super().setData(index, value, role)
	def _index_is_valid(self, index):
		if not index.isValid() or index.model() != self:
			return False
		return 0 <= index.row() < self.rowCount() and \
			   0 <= index.column() < self.columnCount()
	def _on_file_renamed(self, old_path, new_path):
		if dirname(old_path) != self._root_path:
			return
		index = self.index(old_path)
		if dirname(new_path) == self._root_path:
			self._items[index.row()] = new_path
			self.dataChanged.emit(index, index)
		else:
			self._remove_item(index.row())
	def _on_file_removed(self, file_path):
		if dirname(file_path) != self._root_path:
			return
		self._remove_item(self._items.index(file_path))
	def _remove_item(self, row):
		self.beginRemoveRows(QModelIndex(), row, row)
		del self._items[row]
		self.endRemoveRows()

class FileSystem:
	def listdir(self, path):
		return listdir_absolute(path)
	def isdir(self, path):
		return isdir(path)
	def getsize(self, path):
		return getsize(path)
	def getmtime(self, path):
		return getmtime(path)
	def rename(self, old_path, new_path):
		rename(old_path, new_path)
	def move_to_trash(self, file_path):
		move_to_trash(file_path)

class CachedFileSystem(QObject):

	file_renamed = pyqtSignal(str, str)
	file_removed = pyqtSignal(str)

	def __init__(self, source):
		super().__init__()
		self._source = source
		self._cache = {}
	def listdir(self, path):
		result = self._query_cache(path, 'dirs', self._source.listdir)
		# Provide a copy of the list to ensure the caller doesn't accidentally
		# modify the state shared with other incovations:
		return result[::]
	def isdir(self, path):
		return self._query_cache(path, 'isdir', self._source.isdir)
	def getsize(self, path):
		return self._query_cache(path, 'size', self._source.getsize)
	def getmtime(self, path):
		return self._query_cache(path, 'mtime', self._source.getmtime)
	def rename(self, old_path, new_path):
		self._source.rename(old_path, new_path)
		try:
			self._cache[new_path] = self._cache.pop(old_path)
		except KeyError:
			pass
		self.file_renamed.emit(old_path, new_path)
	def move_to_trash(self, file_path):
		self._source.move_to_trash(file_path)
		try:
			del self._cache[file_path]
		except KeyError:
			pass
		self.file_removed.emit(file_path)
	def _query_cache(self, path, item, get_default):
		try:
			cache = self._cache[path]
		except KeyError:
			result = get_default(path)
			self._cache[path] = {
				item: result
			}
			return result
		else:
			if item not in cache:
				try:
					cache[item] = get_default(path)
				except FileNotFoundError:
					del self._cache[path]
					raise
			return cache[item]

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
		column = source.columns[self.sortColumn()]
		left = source.filePath(left)
		right = source.filePath(right)
		is_ascending = self.sortOrder() == AscendingOrder
		return column.less_than(left, right, is_ascending)
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
	def less_than(cls, left, right, is_ascending=True):
		"""
		less_than(...) should generally be independent of is_ascending.
		When is_ascending is False, Qt simply reverses the sort order.
		However, we may sometimes want to change the sort order in a way other
		than a simple reversal when is_ascending is False. That's why this
		method receives is_ascending as a parameter.
		"""
		raise NotImplementedError()

class ValueComparingColumn(Column):
	def less_than(self, left, right, is_ascending=True):
		if self.fs.isdir(left) != self.fs.isdir(right):
			return (self.fs.isdir(left) > self.fs.isdir(right)) == is_ascending
		left_value, right_value = map(self._get_value, (left, right))
		return left_value < right_value
	def _get_value(self, left_or_right):
		raise NotImplementedError()

class NameColumn(ValueComparingColumn):

	name = 'Name'

	def get_str(self, file_path):
		return basename(file_path)
	def _get_value(self, left_or_right):
		return basename(left_or_right).lower()

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
	def less_than(self, left, right, is_ascending=True):
		if self.fs.isdir(left) != self.fs.isdir(right):
			return (self.fs.isdir(left) > self.fs.isdir(right)) == is_ascending
		if self.fs.isdir(left):
			assert self.fs.isdir(right)
			# Sort by name:
			return (basename(left).lower() < basename(right).lower()) \
				   == is_ascending
		return self.fs.getsize(left) < self.fs.getsize(right)

class LastModifiedColumn(ValueComparingColumn):

	name = 'Modified'

	def get_str(self, file_path):
		try:
			modified = datetime.fromtimestamp(self.fs.getmtime(file_path))
		except OSError:
			return ''
		return modified.strftime('%Y-%m-%d %H:%M')
	def _get_value(self, left_or_right):
		return self.fs.getmtime(left_or_right)

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
			pass
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