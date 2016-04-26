from fman.qt_constants import AscendingOrder, WA_MacShowFocusRect, \
	TextAlignmentRole, AlignVCenter, ClickFocus
from PyQt5.QtWidgets import QFileSystemModel, QTreeView, QWidget, QSplitter, \
	QLineEdit, QVBoxLayout, QStyle
from PyQt5.QtCore import QSortFilterProxyModel

def get_main_window(left_path, right_path):
	result = QSplitter()
	left = DirectoryPane()
	left.set_path(left_path)
	right = DirectoryPane()
	right.set_path(right_path)
	result.addWidget(left)
	result.addWidget(right)
	result.setWindowTitle("fman")
	result.resize(762, 300)
	return result

class DirectoryPane(QWidget):
	def __init__(self):
		super().__init__()
		self._path_view = PathView()
		self._file_view = FileListView()
		self._model = FileSystemModel()
		self._model_sorted = SortDirectoriesBeforeFiles(self)
		self._model_sorted.setSourceModel(self._model)
		self._file_view.setModel(self._model_sorted)
		self.setLayout(Layout(self._path_view, self._file_view))
	def set_path(self, path):
		self._model.setRootPath(path)
		index = self._model_sorted.mapFromSource(self._model.index(path))
		self._path_view.setText(path)
		self._file_view.setRootIndex(index)
		self._file_view.hideColumn(2)
		self._file_view.setColumnWidth(0, 200)
		self._file_view.setColumnWidth(1, 75)

class PathView(QLineEdit):
	def __init__(self):
		super().__init__()
		self.setFocusPolicy(ClickFocus)
		self.setAttribute(WA_MacShowFocusRect, 0)

class FileListView(QTreeView):
	def __init__(self):
		super().__init__()
		self.setItemsExpandable(False)
		self.setRootIsDecorated(False)
		self.setSelectionMode(self.ExtendedSelection)
		self.setAllColumnsShowFocus(True)
		self.setAnimated(False)
		self.setSortingEnabled(True)
		self.sortByColumn(0, AscendingOrder)
		self.setAttribute(WA_MacShowFocusRect, 0)
	def drawRow(self, painter, option, index):
		# Even with allColumnsShowFocus set to True, QTreeView::item:focus only
		# styles the first column. Fix this:
		if index.row() == self.currentIndex().row():
			option.state |= QStyle.State_HasFocus
		super().drawRow(painter, option, index)

class FileSystemModel(QFileSystemModel):
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
			return self._always_ascending(left_.fileName() > right_.fileName())
		return self._get_sort_value(left) < self._get_sort_value(right)
	def _get_sort_value(self, row):
		file_info = self.sourceModel().fileInfo(row)
		column = self.sortColumn()
		# QFileSystemModel hardcodes the columns as follows:
		if column == 0:
			return file_info.fileName()
		elif column == 1:
			return file_info.size()
		elif column == 2:
			return self.sourceModel().type(row)
		elif column == 3:
			return file_info.lastModified()
		raise ValueError('Unknown column: %r' % column)
	def _always_ascending(self, value):
		return (self.sortOrder() == AscendingOrder) != bool(value)

class Layout(QVBoxLayout):
	def __init__(self, path_view, file_view):
		super().__init__()
		self.addWidget(path_view)
		self.addWidget(file_view)
		self.setContentsMargins(0, 0, 0, 0)
		self.setSpacing(0)