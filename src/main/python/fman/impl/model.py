from fman.util.qt import TextAlignmentRole, AlignVCenter, ItemIsEnabled, \
	ItemIsEditable, ItemIsSelectable, EditRole, AscendingOrder
from PyQt5.QtCore import pyqtSignal, QModelIndex, QSortFilterProxyModel
from PyQt5.QtWidgets import QFileSystemModel

class FileSystemModel(QFileSystemModel):

	file_renamed = pyqtSignal(QFileSystemModel, QModelIndex, str)

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
			self.file_renamed.emit(self, index, value)
			return True
		return super().setData(index, value, role)

class SortDirectoriesBeforeFiles(QSortFilterProxyModel):
	def lessThan(self, left, right):
		column = _COLUMNS[self.sortColumn()]
		is_ascending = self.sortOrder() == AscendingOrder
		left_info = self.sourceModel().fileInfo(left)
		right_info = self.sourceModel().fileInfo(right)
		return column.less_than(left_info, right_info, is_ascending)

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