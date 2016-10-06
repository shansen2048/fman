from fman import OK
from fman.impl.model import FileSystemModel, SortDirectoriesBeforeFiles
from fman.impl.view import FileListView, Layout, PathView
from fman.util.qt import connect_once, run_in_main_thread
from os.path import abspath, exists, join, pardir
from PyQt5.QtCore import QDir, pyqtSignal
from PyQt5.QtWidgets import QWidget, QMainWindow, QSplitter, QStatusBar, \
	QMessageBox, QInputDialog, QLineEdit, QFileDialog

class DirectoryPane(QWidget):
	def __init__(self, parent):
		super().__init__(parent)
		self._path_view = PathView(self)
		self._model = FileSystemModel()
		self._model.setFilter(self._model.filter() | QDir.Hidden | QDir.System)
		self._model.file_edited.connect(self._on_file_renamed)
		self._model_sorted = SortDirectoriesBeforeFiles(self)
		self._model_sorted.setSourceModel(self._model)
		self._file_view = FileListView(self)
		self._file_view.setModel(self._model_sorted)
		self._file_view.doubleClicked.connect(self._on_doubleclicked)
		self._file_view.keyPressEventFilter = self._on_key_pressed
		self.setLayout(Layout(self._path_view, self._file_view))
		self._controller = None
	def set_controller(self, controller):
		self._controller = controller
	def move_cursor_up(self, toggle_selection=False):
		self._file_view.move_cursor_up(toggle_selection)
	def move_cursor_down(self, toggle_selection=False):
		self._file_view.move_cursor_down(toggle_selection)
	def move_cursor_home(self, toggle_selection=False):
		self._file_view.move_cursor_home(toggle_selection)
	def move_cursor_end(self, toggle_selection=False):
		self._file_view.move_cursor_end(toggle_selection)
	def move_cursor_page_up(self, toggle_selection=False):
		self._file_view.move_cursor_page_up(toggle_selection)
	def move_cursor_page_down(self, toggle_selection=False):
		self._file_view.move_cursor_page_down(toggle_selection)
	def toggle_selection(self, file_path):
		self._file_view.toggle_selection(file_path)
	def select_all(self):
		self._file_view.selectAll()
	def get_selected_files(self):
		return self._file_view.get_selected_files()
	def get_file_under_cursor(self):
		return self._file_view.get_file_under_cursor()
	def get_path(self):
		return abspath(self._model.rootPath())
	def set_path(self, path, callback=None):
		if callback is None:
			callback = self._file_view.reset_cursor
		path = self._normalize_path(path)
		if path == self.get_path():
			# Don't mess up the cursor if we're already in the right location.
			return
		self._file_view.reset()
		self._path_view.setText(path)
		connect_once(self._model.directoryLoaded, lambda _: callback())
		index = self._model_sorted.mapFromSource(self._model.setRootPath(path))
		self._file_view.setRootIndex(index)
		self._file_view.hideColumn(2)
	def place_cursor_at(self, file_path):
		self._file_view.place_cursor_at(file_path)
	def edit_name(self, file_path):
		self._file_view.edit_name(file_path)
	def add_filter(self, filter_):
		self._model_sorted.add_filter(filter_)
	def invalidate_filter(self):
		return self._model_sorted.invalidateFilter()
	@property
	def window(self):
		return self.parentWidget().parentWidget()
	def get_column_widths(self):
		return [self._file_view.columnWidth(i) for i in (0, 1)]
	def set_column_widths(self, column_widths):
		for i, width in enumerate(column_widths):
			self._file_view.setColumnWidth(i, width)
	def _normalize_path(self, path):
		path = abspath(path)
		while not exists(path):
			new_path = abspath(join(path, pardir))
			if path == new_path:
				break
			path = new_path
		return path
	def _on_doubleclicked(self, index):
		self._controller.on_doubleclicked(
			self, self._model.filePath(self._model_sorted.mapToSource(index))
		)
	def _on_key_pressed(self, file_view, event):
		return self._controller.on_key_pressed(self, event)
	def _on_file_renamed(self, index, new_name):
		file_path = self._model.filePath(index)
		self._controller.on_file_renamed(self, file_path, new_name)

class MainWindow(QMainWindow):

	pane_added = pyqtSignal(DirectoryPane)

	def __init__(self, controller):
		super().__init__()
		self.controller = controller
		self.panes = []
		self.splitter = QSplitter(self)
		self.setCentralWidget(self.splitter)
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
	def add_pane(self):
		result = DirectoryPane(self.splitter)
		result.set_controller(self.controller)
		self.panes.append(result)
		self.splitter.addWidget(result)
		self.pane_added.emit(result)
		return result
	def get_panes(self):
		return self.panes