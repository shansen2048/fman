from fman.impl.controller import DirectoryPaneController
from fman.impl.model import FileSystemModel, SortDirectoriesBeforeFiles
from fman.impl.view import FileListView, Layout, PathView
from fman.util.qt import connect_once
from PyQt5.QtWidgets import QSplitter, QWidget

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
		self._controller = DirectoryPaneController(self)
		self._path_view = PathView()
		self._model = FileSystemModel()
		self._model.file_renamed.connect(self._controller.file_renamed)
		self._model_sorted = SortDirectoriesBeforeFiles(self)
		self._model_sorted.setSourceModel(self._model)
		self._file_view = FileListView(self._model_sorted, self._controller)
		self._file_view.activated.connect(self._activated)
		self.setLayout(Layout(self._path_view, self._file_view))
	def set_path(self, path, callback=None):
		if callback is None:
			callback = self.reset_cursor
		self._file_view.reset()
		connect_once(self._model.directoryLoaded, lambda _: callback())
		self._model.setRootPath(path)
		self._path_view.setText(path)
		self._file_view.setRootIndex(self._root_index)
		self._file_view.hideColumn(2)
		self._file_view.setColumnWidth(0, 200)
		self._file_view.setColumnWidth(1, 75)
	def get_path(self):
		return self._model.rootPath()
	def place_cursor_at(self, path):
		self._file_view.setCurrentIndex(self._path_to_index(path))
	def reset_cursor(self):
		self._file_view.setCurrentIndex(self._root_index.child(0, 0))
	@property
	def _root_index(self):
		return self._path_to_index(self._model.rootPath())
	def _path_to_index(self, path):
		return self._model_sorted.mapFromSource(self._model.index(path))
	def _activated(self, index):
		model_index = self._model_sorted.mapToSource(index)
		self._controller.activated(self._model, self._file_view, model_index)