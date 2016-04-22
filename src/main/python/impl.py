from PyQt5.QtWidgets import QApplication, QFileSystemModel, QTreeView, QWidget,\
	QHBoxLayout, QVBoxLayout, QSplitter, QLineEdit
from PyQt5.QtCore import QSortFilterProxyModel
from PyQt5 import QtCore

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

	tree.setAnimated(False)
	tree.setSortingEnabled(True)
	# Don't display "kind" column:
	tree.hideColumn(2)
	# Hide blue glow on Mac when the tree has focus:
	edit.setAttribute(QtCore.Qt.WA_MacShowFocusRect, 0)
	tree.setAttribute(QtCore.Qt.WA_MacShowFocusRect, 0)
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
		if role == QtCore.Qt.TextAlignmentRole and value is not None:
			# The standard QFileSystemModel messes up the vertical alignment of
			# the "Size" column. Work around this
			# (http://stackoverflow.com/a/20233442/1839209):
			value |= QtCore.Qt.AlignVCenter
		return value
	def headerData(self, section, orientation, role):
		result = super().headerData(section, orientation, role)
		if result == 'Date Modified':
			return 'Modified'
		return result

class SortDirectoriesBeforeFiles(QSortFilterProxyModel):
	def lessThan(self, left, right):
		leftInfo = self.sourceModel().fileInfo(left)
		rightInfo = self.sourceModel().fileInfo(right)
		leftTpl = (not leftInfo.isDir(), leftInfo.fileName())
		rightTpl = (not rightInfo.isDir(), rightInfo.fileName())
		return leftTpl < rightTpl