from fman import OK
from fman.impl.model import FileSystemModel, SortDirectoriesBeforeFiles
from fman.impl.view import FileListView, Layout, PathView, QuickSearch
from fman.util.qt import connect_once, run_in_main_thread
from os.path import exists, normpath, dirname
from PyQt5.QtCore import QDir, pyqtSignal, QTimer
from PyQt5.QtWidgets import QWidget, QMainWindow, QSplitter, QStatusBar, \
	QMessageBox, QInputDialog, QLineEdit, QFileDialog, QLabel

class DirectoryPane(QWidget):

	path_changed = pyqtSignal(QWidget)

	def __init__(self, parent, icon_provider=None):
		super().__init__(parent)
		self._path_view = PathView(self)
		self._model = FileSystemModel()
		if icon_provider is not None:
			self._model.setIconProvider(icon_provider)
		self._model.setFilter(self._model.filter() | QDir.Hidden | QDir.System)
		self._model.file_renamed.connect(self._on_file_renamed)
		self._model.files_dropped.connect(self._on_files_dropped)
		self._model_sorted = SortDirectoriesBeforeFiles(self)
		self._model_sorted.setSourceModel(self._model)
		self._file_view = FileListView(self)
		self._file_view.setModel(self._model_sorted)
		self._file_view.doubleClicked.connect(self._on_doubleclicked)
		self._file_view.keyPressEventFilter = self._on_key_pressed
		self._file_view.hideColumn(2)
		self.setLayout(Layout(self._path_view, self._file_view))
		self._controller = None
	@property
	def id(self):
		return id(self)
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
		result = self._model.rootPath()
		if not result:
			# Displaying "My Computer" - see QFileSystemModel#myComputer()
			return ''
		return normpath(result)
	def set_path(self, path, callback=None):
		if callback is None:
			callback = self._file_view.reset_cursor
		if path == self.get_path():
			# Don't mess up the cursor if we're already in the right location.
			return
		my_computer = self._model.myComputer()
		path = self._skip_to_existing_pardir(path) if path else my_computer
		self._file_view.reset()
		self._path_view.setText(path)
		if path == my_computer:
			# directoryLoaded doesn't work for myComputer. Use rootPathChanged:
			signal = self._model.rootPathChanged
		else:
			signal = self._model.directoryLoaded
		def callback_():
			self.path_changed.emit(self)
			callback()
		connect_once(signal, lambda _: callback_())
		index = self._model_sorted.setRootPath(path)
		self._file_view.setRootIndex(index)
	def place_cursor_at(self, file_path):
		self._file_view.place_cursor_at(file_path)
	def edit_name(self, file_path):
		self._file_view.edit_name(file_path)
	def add_filter(self, filter_):
		self._model_sorted.add_filter(filter_)
	def invalidate_filters(self):
		self._model_sorted.invalidateFilter()
	@property
	def window(self):
		return self.parentWidget().parentWidget()
	def get_column_widths(self):
		return [self._file_view.columnWidth(i) for i in (0, 1)]
	def set_column_widths(self, column_widths):
		for i, width in enumerate(column_widths):
			self._file_view.setColumnWidth(i, width)
	def _skip_to_existing_pardir(self, path):
		path = normpath(path)
		while not exists(path):
			new_path = dirname(path)
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
	def _on_file_renamed(self, *args):
		self._controller.on_file_renamed(self, *args)
	def _on_files_dropped(self, *args):
		self._controller.on_files_dropped(self, *args)

class MainWindow(QMainWindow):

	pane_added = pyqtSignal(DirectoryPane)
	shown = pyqtSignal()

	def __init__(self, icon_provider=None):
		super().__init__()
		self.icon_provider = icon_provider
		self.controller = None
		self.panes = []
		self.splitter = QSplitter(self)
		self.setCentralWidget(self.splitter)
		self.status_bar = QStatusBar(self)
		self.status_bar_text = QLabel(self.status_bar)
		self.status_bar_text.setOpenExternalLinks(True)
		self.status_bar.addWidget(self.status_bar_text)
		self.status_bar.setSizeGripEnabled(False)
		self.setStatusBar(self.status_bar)
		self.setWindowTitle("fman")
		self.timer = QTimer(self)
		self.timer.timeout.connect(self.clear_status_message)
		self.timer.setSingleShot(True)
	def set_controller(self, controller):
		self.controller = controller
	@run_in_main_thread
	def show_alert(self, text, buttons=OK, default_button=OK):
		msgbox = QMessageBox(self)
		# API users might pass arbitrary objects as text when trying to debug,
		# eg. exception instances. Convert to str(...) to allow for this:
		msgbox.setText(str(text))
		msgbox.setStandardButtons(buttons)
		msgbox.setDefaultButton(default_button)
		return msgbox.exec()
	@run_in_main_thread
	def show_file_open_dialog(self, caption, dir_path, filter_text):
		# Let API users pass arbitrary objects by converting with str(...):
		return QFileDialog.getOpenFileName(
			self, str(caption), str(dir_path), str(filter_text)
		)
	@run_in_main_thread
	def show_prompt(self, text, default=''):
		# Let API users pass arbitrary objects by converting with str(...):
		return QInputDialog.getText(
			self, 'fman', str(text), QLineEdit.Normal, str(default)
		)
	@run_in_main_thread
	def show_quicksearch(self, get_suggestions, get_tab_completion):
		return QuickSearch(self, get_suggestions, get_tab_completion).exec()
	@run_in_main_thread
	def show_status_message(self, text, timeout_secs=None):
		self.status_bar_text.setText(text)
		if timeout_secs:
			self.timer.start(int(timeout_secs * 1000))
		else:
			self.timer.stop()
	def clear_status_message(self):
		self.show_status_message('Ready.')
	def add_pane(self):
		result = DirectoryPane(self.splitter, self.icon_provider)
		result.set_controller(self.controller)
		self.panes.append(result)
		self.splitter.addWidget(result)
		self.pane_added.emit(result)
		return result
	def get_panes(self):
		return self.panes
	def showEvent(self, *args):
		super().showEvent(*args)
		QTimer(self).singleShot(0, self.shown.emit)