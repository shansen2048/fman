from fman.util.qt import TextAlignmentRole, AlignVCenter, ItemIsEnabled, \
	ItemIsEditable, ItemIsSelectable, EditRole, AscendingOrder
from os.path import commonprefix
from PyQt5.QtCore import pyqtSignal, QModelIndex, QSortFilterProxyModel
from PyQt5.QtWidgets import QFileSystemModel

class FileSystemModel(QFileSystemModel):

	file_edited = pyqtSignal(QModelIndex, str)

	def data(self, index, role):
		value = super(FileSystemModel, self).data(index, role)
		if role == TextAlignmentRole and value is not None:
			# The standard QFileSystemModel messes up the vertical alignment of
			# the "Size" column. Work around this
			# (http://stackoverflow.com/a/20233442/1839209):
			value |= AlignVCenter
		return value
	def headerData(self, section, orientation, role):
		result = super().headerData(section, orientation, role)
		if result == 'Date Modified':
			return 'Modified'
		return result
	def flags(self, index):
		return ItemIsEnabled | ItemIsEditable | ItemIsSelectable
	def setData(self, index, value, role):
		if role == EditRole:
			self.file_edited.emit(index, value)
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