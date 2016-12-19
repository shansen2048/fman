from fman.util.qt import TextAlignmentRole, AlignVCenter, ItemIsEnabled, \
	ItemIsEditable, ItemIsSelectable, EditRole, AscendingOrder, DisplayRole, \
	ItemIsDragEnabled, ItemIsDropEnabled, CopyAction, MoveAction, IgnoreAction
from os.path import commonprefix, isdir, dirname
from PyQt5.QtCore import pyqtSignal, QSortFilterProxyModel, QFileInfo, \
	QLocale, QVariant, QUrl, QMimeData
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QFileSystemModel, QFileIconProvider

import sip
import sys

class FileSystemModel(QFileSystemModel):

	file_renamed = pyqtSignal(str, str)
	files_dropped = pyqtSignal(list, str, bool)

	def data(self, index, role):
		# Copied from QFileSystemModel:
		if not index.isValid() or index.model() != self:
			return QVariant()
		if role == DisplayRole and index.column() == _LAST_MODIFIED_COLUMN:
			datetime_format = QLocale().dateTimeFormat(QLocale.ShortFormat)
			# In December 2016, Qt started displaying the modified time as
			# "...yyyy" instead of "...yy" on my Mac. The default implementation
			# of QFileSystemModel uses the system locale (not! the default
			# locale, which we could override) to textualise times. On that Mac,
			# the system locale had the surprising property that
			#     system.dateTimeFormat()
			#              !=
			#     QLocale(system.language(), system.country()).dateTimeFormat()
			# (where system = QLocale.system()).
			# Anyways, we want short 2-year dates instead of long 4-year dates:
			datetime_format = datetime_format.replace('yyyy', 'yy')
			return self.lastModified(index).toString(datetime_format)
		value = super(FileSystemModel, self).data(index, role)
		if role == TextAlignmentRole and value is not None:
			# The standard QFileSystemModel messes up the vertical alignment of
			# the "Size" column. Work around this
			# (http://stackoverflow.com/a/20233442/1839209):
			value |= AlignVCenter
		return value
	def supportedDropActions(self):
		return MoveAction | CopyAction | IgnoreAction
	def canDropMimeData(self, data, action, row, column, parent):
		if not action & self.supportedDropActions():
			return False
		if not data.hasUrls():
			return False
		if not parent.isValid():
			return False
		dest_dir = self.filePath(parent)
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
		if not parent.isValid():
			return False
		dest = self.filePath(parent)
		if not isdir(dest):
			return False
		urls = [url.toLocalFile() for url in data.urls()]
		if action == MoveAction:
			self.files_dropped.emit(urls, dest, False)
			return True
		if action == CopyAction:
			self.files_dropped.emit(urls, dest, True)
			return True
		return False
	def headerData(self, section, orientation, role):
		result = super().headerData(section, orientation, role)
		if result == 'Date Modified':
			return 'Modified'
		return result
	def flags(self, index):
		result = ItemIsEnabled | ItemIsEditable | ItemIsSelectable
		if index.column() == 0:
			result |= ItemIsDragEnabled
			if self.isDir(index):
				result |= ItemIsDropEnabled
		return result
	def setData(self, index, value, role):
		if role == EditRole:
			self.file_renamed.emit(self.filePath(index), value)
			return True
		return super().setData(index, value, role)

class SortDirectoriesBeforeFiles(QSortFilterProxyModel):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.filters = []
	def lessThan(self, left, right):
		column = _COLUMNS[self.sortColumn()]
		is_ascending = self.sortOrder() == AscendingOrder
		left_info = self.sourceModel().fileInfo(left)
		right_info = self.sourceModel().fileInfo(right)
		return column.less_than(left_info, right_info, is_ascending)
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
		if left.isDir() != right.isDir():
			return (left.isDir() > right.isDir()) == is_ascending
		left_value, right_value = map(cls._get_value, (left, right))
		return left_value < right_value
	@classmethod
	def _get_value(cls, left_or_right):
		raise NotImplementedError()

class NameColumn(ValueComparingColumn):
	@classmethod
	def _get_value(cls, left_or_right):
		return left_or_right.fileName().lower()

class SizeColumn(Column):
	@classmethod
	def less_than(cls, left, right, is_ascending=True):
		if left.isDir() != right.isDir():
			return (left.isDir() > right.isDir()) == is_ascending
		if left.isDir():
			assert right.isDir()
			return NameColumn().less_than(left, right, True) == is_ascending
		return left.size() < right.size()

class TypeColumn(Column):
	@classmethod
	def less_than(cls, left, right, is_ascending=True):
		raise NotImplementedError()

class LastModifiedColumn(ValueComparingColumn):
	@classmethod
	def _get_value(cls, left_or_right):
		return left_or_right.lastModified()

_COLUMNS = (NameColumn, SizeColumn, TypeColumn, LastModifiedColumn)
_LAST_MODIFIED_COLUMN = _COLUMNS.index(LastModifiedColumn)

class UbuntuFileIconProvider(QFileIconProvider):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.Gtk, self.Gio = self._init_pgi()
	def _init_pgi(self):
		import pgi
		pgi.install_as_gi()
		import gi
		gi.require_version('Gtk', '3.0')
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