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
		left_ = self.sourceModel().fileInfo(left)
		right_ = self.sourceModel().fileInfo(right)
		left_is_dir = left_.isDir()
		right_is_dir = right_.isDir()
		# Always show directories at the top:
		if left_is_dir != right_is_dir:
			return self._always_ascending(left_is_dir < right_is_dir)
		if left_is_dir and right_is_dir:
			# Sort directories by name:
			return self._always_ascending(
				left_.fileName().lower() > right_.fileName().lower()
			)
		return self._get_sort_value(left) < self._get_sort_value(right)
	def _get_sort_value(self, row):
		file_info = self.sourceModel().fileInfo(row)
		column = self.sortColumn()
		# QFileSystemModel hardcodes the columns as follows:
		if column == 0:
			return file_info.fileName().lower()
		elif column == 1:
			return file_info.size()
		elif column == 2:
			return self.sourceModel().type(row)
		elif column == 3:
			return file_info.lastModified()
		raise ValueError('Unknown column: %r' % column)
	def _always_ascending(self, value):
		return (self.sortOrder() == AscendingOrder) != bool(value)