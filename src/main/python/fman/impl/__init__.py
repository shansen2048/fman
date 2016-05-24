from fman.impl.controller import DirectoryPaneController
from fman.impl.model import FileSystemModel, SortDirectoriesBeforeFiles
from fman.impl.view import FileListView, Layout, PathView
from fman.util.qt import connect_once
from PyQt5.QtWidgets import QWidget

class DirectoryPane(QWidget):
	def __init__(self, controller):
		super().__init__()
		self._path_view = PathView(self)
		self._model = FileSystemModel()
		file_renamed = lambda *args: controller.file_renamed(self, *args)
		self._model.file_renamed.connect(file_renamed)
		self._model_sorted = SortDirectoriesBeforeFiles(self)
		self._model_sorted.setSourceModel(self._model)
		self.file_view = FileListView(self)
		self.file_view.setModel(self._model_sorted)
		self.file_view.keyPressEventFilter = controller.key_pressed_in_file_view
		self.file_view.activated.connect(self._activated)
		self.setLayout(Layout(self._path_view, self.file_view))
		self._controller = controller
	def set_path(self, path, callback=None):
		if callback is None:
			callback = self.reset_cursor
		self.file_view.reset()
		connect_once(self._model.directoryLoaded, lambda _: callback())
		self._model.setRootPath(path)
		self._path_view.setText(path)
		self.file_view.setRootIndex(self._root_index)
		self.file_view.hideColumn(2)
	def get_path(self):
		return self._model.rootPath()
	def place_cursor_at(self, path):
		self.file_view.setCurrentIndex(self._path_to_index(path))
	def reset_cursor(self):
		self.file_view.setCurrentIndex(self._root_index.child(0, 0))
	@property
	def _root_index(self):
		return self._path_to_index(self._model.rootPath())
	def _path_to_index(self, path):
		return self._model_sorted.mapFromSource(self._model.index(path))
	def _activated(self, index):
		model_index = self._model_sorted.mapToSource(index)
		self._controller.activated(self._model, self.file_view, model_index)