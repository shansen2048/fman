from datetime import datetime
from fman.util import listdir_absolute
from fman.util.qt import ItemIsEnabled, ItemIsEditable, ItemIsSelectable, \
	EditRole, AscendingOrder, DisplayRole, ItemIsDragEnabled, \
	ItemIsDropEnabled, CopyAction, MoveAction, IgnoreAction, DecorationRole
from math import log
from os.path import commonprefix, isdir, dirname, normpath, basename, \
	getmtime, getsize
from PyQt5.QtCore import pyqtSignal, QSortFilterProxyModel, QFileInfo, \
	QVariant, QUrl, QMimeData, QAbstractTableModel, QModelIndex, Qt
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

	def __init__(self, icon_provider=None, parent=None):
		super().__init__(parent)
		self._items = []
		self._root_path = ''
		self._icon_provider = icon_provider
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
		return len(_COLUMNS)
	def data(self, index, role=DisplayRole):
		if self._index_is_valid(index):
			if role in (DisplayRole, EditRole):
				column = _COLUMNS[index.column()]
				return QVariant(column.get_str(self._items[index.row()]))
			elif role == DecorationRole:
				if self._icon_provider and index.column() == 0:
					file_info = QFileInfo(self.filePath(index))
					return self._icon_provider.icon(file_info)
		return QVariant()
	def headerData(self, section, orientation, role=DisplayRole):
		if orientation == Qt.Horizontal and role == DisplayRole \
			and 0 <= section < self.columnCount():
			return QVariant(_COLUMNS[section].name)
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
			self._items = listdir_absolute(path)
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
			if isdir(self.filePath(index)):
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
		column = _COLUMNS[self.sortColumn()]
		is_ascending = self.sortOrder() == AscendingOrder
		left = self.sourceModel().filePath(left)
		right = self.sourceModel().filePath(right)
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
	@classmethod
	def get_str(cls, file_path):
		raise NotImplementedError()
	@classmethod
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
	@classmethod
	def less_than(cls, left, right, is_ascending=True):
		if isdir(left) != isdir(right):
			return (isdir(left) > isdir(right)) == is_ascending
		left_value, right_value = map(cls._get_value, (left, right))
		return left_value < right_value
	@classmethod
	def _get_value(cls, left_or_right):
		raise NotImplementedError()

class NameColumn(ValueComparingColumn):

	name = 'Name'

	@classmethod
	def get_str(cls, file_path):
		return basename(file_path)
	@classmethod
	def _get_value(cls, left_or_right):
		return basename(left_or_right).lower()

class SizeColumn(Column):

	name = 'Size'

	@classmethod
	def get_str(cls, file_path):
		if isdir(file_path):
			return ''
		size_bytes = getsize(file_path)
		units = ('%d bytes', '%d KB', '%.1f MB', '%.1f GB')
		if size_bytes <= 0:
			unit_index = 0
		else:
			unit_index = min(int(log(size_bytes, 1024)), len(units) - 1)
		unit = units[unit_index]
		base = 1024 ** unit_index
		return unit % (size_bytes / base)
	@classmethod
	def less_than(cls, left, right, is_ascending=True):
		if isdir(left) != isdir(right):
			return (isdir(left) > isdir(right)) == is_ascending
		if isdir(left):
			assert isdir(right)
			return NameColumn().less_than(left, right, True) == is_ascending
		return getsize(left) < getsize(right)

class LastModifiedColumn(ValueComparingColumn):

	name = 'Modified'

	@classmethod
	def get_str(cls, file_path):
		try:
			modified = datetime.fromtimestamp(getmtime(file_path))
		except OSError:
			return ''
		return modified.strftime('%Y-%m-%d %H:%M')
	@classmethod
	def _get_value(cls, left_or_right):
		return getmtime(left_or_right)

_COLUMNS = (NameColumn, SizeColumn, LastModifiedColumn)
_LAST_MODIFIED_COLUMN = _COLUMNS.index(LastModifiedColumn)

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
			file_path = arg.absoluteFilePath()
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
							result = self._load_gtk_icon(icon_names[0])
		return result or super().icon(arg)
	def _load_gtk_icon(self, name, size=32):
		theme = self.Gtk.IconTheme.get_default()
		if theme:
			icon = theme.lookup_icon(name, size, 0)
			if icon:
				return QIcon(icon.get_filename())

class GnomeNotAvailable(RuntimeError):
	pass