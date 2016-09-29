from fman import OK
from fman.impl.model import FileSystemModel, SortDirectoriesBeforeFiles
from fman.impl.view import FileListView, Layout, PathView
from fman.util.qt import connect_once, run_in_main_thread
from os.path import abspath, exists, join, pardir
from PyQt5.QtWidgets import QWidget, QMainWindow, QSplitter, QStatusBar, \
	QMessageBox, QInputDialog, QLineEdit, QFileDialog

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
	@run_in_main_thread
	def show_alert(self, text, buttons=OK, default_button=OK):
		msgbox = QMessageBox(self)
		msgbox.setText(text)
		msgbox.setStandardButtons(buttons)
		msgbox.setDefaultButton(default_button)
		return msgbox.exec()
	@run_in_main_thread
	def show_file_open_dialog(self, caption, dir_path, filter_text):
		return QFileDialog.getOpenFileName(self, caption, dir_path, filter_text)
	@run_in_main_thread
	def show_prompt(self, text, default=''):
		return QInputDialog.getText(
			self, 'fman', text, QLineEdit.Normal, default
		)
	@run_in_main_thread
	def show_status_message(self, text):
		self.status_bar.showMessage(text)
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
	def move_cursor_up(self, toggle_current=False):
		self.file_view.move_cursor_up(toggle_current)
	def move_cursor_down(self, toggle_current=False):
		self.file_view.move_cursor_down(toggle_current)
	def move_cursor_home(self, toggle_current=False):
		self.file_view.move_cursor_home(toggle_current)
	def move_cursor_end(self, toggle_current=False):
		self.file_view.move_cursor_end(toggle_current)
	def move_cursor_page_up(self, toggle_current=False):
		self.file_view.move_cursor_page_up(toggle_current)
	def move_cursor_page_down(self, toggle_current=False):
		self.file_view.move_cursor_page_down(toggle_current)
	def toggle_selection(self, file_path):
		self.file_view.toggle_selection(file_path)
	def select_all(self):
		self.file_view.selectAll()
	def get_selected_files(self):
		return self.file_view.get_selected_files()
	def get_file_under_cursor(self):
		return self.file_view.get_file_under_cursor()
	def get_path(self):
		return abspath(self._model.rootPath())
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
	def place_cursor_at(self, file_path):
		self.file_view.place_cursor_at(file_path)
	def rename(self, file_path):
		self.file_view.rename(file_path)
	def open(self, file_path):
		self.file_view.open(file_path)
	def set_filter_flags(self, flags):
		self._model.setFilter(flags)
	def get_filter_flags(self):
		return self._model.filter()
	def _normalize_path(self, path):
		path = abspath(path)
		while not exists(path):
			new_path = abspath(join(path, pardir))
			if path == new_path:
				break
			path = new_path
		return path
	def _activated(self, index):
		model_index = self._model_sorted.mapToSource(index)
		self._controller.activated(self._model, self.file_view, model_index)