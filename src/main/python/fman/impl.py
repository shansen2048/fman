from fman.qt_constants import AscendingOrder, WA_MacShowFocusRect, \
	TextAlignmentRole, AlignVCenter, ClickFocus
from PyQt5.QtWidgets import QFileSystemModel, QTreeView, QWidget, QSplitter, \
	QLineEdit, QVBoxLayout, QStyle
from PyQt5.QtCore import QSortFilterProxyModel

def get_main_window(left_path, right_path):
	result = QSplitter()
	result.addWidget(_get_tree_view(left_path))
	result.addWidget(_get_tree_view(right_path))
	result.setWindowTitle("fman")
	result.resize(762, 300)
	return result

def _get_tree_view(path):
	container = QWidget()
	layout = QVBoxLayout()

	edit = QLineEdit()
	edit.setText(path)
	edit.setFocusPolicy(ClickFocus)
	layout.addWidget(edit)

	model = FileSystemModel()
	model.setRootPath(path)
	model_sorted = SortDirectoriesBeforeFiles(container)
	model_sorted.setSourceModel(model)
	tree = QTreeView()
	tree.setModel(model_sorted)
	tree.setRootIndex(model_sorted.mapFromSource(model.index(path)))
	tree.setItemsExpandable(False)
	tree.setRootIsDecorated(False)
	tree.setSelectionMode(tree.ExtendedSelection)
	tree.setAllColumnsShowFocus(True)

	# Even with allColumnsShowFocus set to True, QTreeView::item:focus only
	# styles the first column. Fix this:
	origDrawRow = tree.drawRow
	def drawRow(painter, option, index):
		if index.row() == tree.currentIndex().row():
			option.state |= QStyle.State_HasFocus
		origDrawRow(painter, option, index)
	tree.drawRow = drawRow

	tree.setAnimated(False)
	tree.setSortingEnabled(True)
	tree.sortByColumn(0, AscendingOrder)
	# Don't display "kind" column:
	tree.hideColumn(2)
	# Hide blue glow on Mac when the tree has focus:
	edit.setAttribute(WA_MacShowFocusRect, 0)
	tree.setAttribute(WA_MacShowFocusRect, 0)
	tree.setColumnWidth(0, 200)
	tree.setColumnWidth(1, 75)
	layout.setContentsMargins(0, 0, 0, 0)
	layout.setSpacing(0)
	layout.addWidget(tree)
	container.setLayout(layout)
	return container

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