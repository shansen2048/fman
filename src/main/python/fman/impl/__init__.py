from fman.impl.model import FileSystemModel, SortDirectoriesBeforeFiles
from fman.impl.view import FileListView, Layout, PathView
from fman.util.qt import connect_once
from os.path import abspath, exists, join, pardir
from PyQt5.QtWidgets import QWidget, QMainWindow, QSplitter, QStatusBar

class MainWindow(QMainWindow):
	def __init__(self):
		super().__init__()
		splitter = QSplitter(self)
		self.left_pane = DirectoryPane(splitter)
		splitter.addWidget(self.left_pane)
		self.right_pane = DirectoryPane(splitter)
		splitter.addWidget(self.right_pane)
		self.setCentralWidget(splitter)
		self.status_bar = QStatusBar(self)
		self.status_bar.setSizeGripEnabled(False)
		self.setStatusBar(self.status_bar)
		self.setWindowTitle("fman")
	def set_controller(self, controller):
		self.left_pane.set_controller(controller)
		self.right_pane.set_controller(controller)

class DirectoryPane(QWidget):
	def __init__(self, parent):
		super().__init__(parent)
		self._path_view = PathView(self)
		self._model = FileSystemModel()
		self._model_sorted = SortDirectoriesBeforeFiles(self)
		self._model_sorted.setSourceModel(self._model)
		self.file_view = FileListView(self)
		self.file_view.setModel(self._model_sorted)
		self.file_view.activated.connect(self._activated)
		self.setLayout(Layout(self._path_view, self.file_view))
		self._controller = None
	def set_controller(self, controller):
		self.file_view.keyPressEventFilter = controller.key_pressed_in_file_view
		file_renamed = lambda *args: controller.file_renamed(self, *args)
		self._model.file_renamed.connect(file_renamed)
		self._controller = controller
	def set_path(self, path, callback=None):
		if callback is None:
			callback = self.file_view.reset_cursor
		path = self._normalize_path(path)
		self.file_view.reset()
		self._path_view.setText(path)
		connect_once(self._model.directoryLoaded, lambda _: callback())
		index = self._model_sorted.mapFromSource(self._model.setRootPath(path))
		self.file_view.setRootIndex(index)
		self.file_view.hideColumn(2)
	def get_path(self):
		return abspath(self._model.rootPath())
	def place_cursor_at(self, path):
		self.file_view.setCurrentIndex(self._path_to_index(path))
	def _normalize_path(self, path):
		path = abspath(path)
		while not exists(path):
			new_path = abspath(join(path, pardir))
			if path == new_path:
				break
			path = new_path
		return path
	def _path_to_index(self, path):
		return self._model_sorted.mapFromSource(self._model.index(path))
	def _activated(self, index):
		model_index = self._model_sorted.mapToSource(index)
		self._controller.activated(self._model, self.file_view, model_index)