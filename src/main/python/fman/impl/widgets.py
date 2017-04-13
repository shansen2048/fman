from fman import OK
from fman.impl.model import FileSystemModel, SortDirectoriesBeforeFiles
from fman.impl.view import FileListView, Layout, PathView, Quicksearch
from fman.util.system import is_windows, is_mac
from fman.util.qt import connect_once, run_in_main_thread, \
	disable_window_animations_mac
from os.path import exists, normpath, dirname, splitdrive
from PyQt5.QtCore import QDir, pyqtSignal, QTimer, Qt, QEvent
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QWidget, QMainWindow, QSplitter, QStatusBar, \
	QMessageBox, QInputDialog, QLineEdit, QFileDialog, QLabel, QDialog, \
	QHBoxLayout, QPushButton, QVBoxLayout, QSplitterHandle, QApplication
from random import randint, randrange

class Application(QApplication):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._main_window = None
	def set_main_window(self, main_window):
		self._main_window = main_window
		# Ensure all other windows are closed as well when the main window
		# is closed. (This in particular closes windows opened by plugins.)
		main_window.closed.connect(self.quit)
	def exit(self, returnCode=0):
		if self._main_window is not None:
			self._main_window.close()
		super().exit(returnCode)

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
		self._path_view.setFocusProxy(self._file_view)
		self.setFocusProxy(self._file_view)
		self._controller = None
	def set_controller(self, controller):
		self._controller = controller
	@run_in_main_thread
	def move_cursor_up(self, toggle_selection=False):
		self._file_view.move_cursor_up(toggle_selection)
	@run_in_main_thread
	def move_cursor_down(self, toggle_selection=False):
		self._file_view.move_cursor_down(toggle_selection)
	@run_in_main_thread
	def move_cursor_home(self, toggle_selection=False):
		self._file_view.move_cursor_home(toggle_selection)
	@run_in_main_thread
	def move_cursor_end(self, toggle_selection=False):
		self._file_view.move_cursor_end(toggle_selection)
	@run_in_main_thread
	def move_cursor_page_up(self, toggle_selection=False):
		self._file_view.move_cursor_page_up(toggle_selection)
	@run_in_main_thread
	def move_cursor_page_down(self, toggle_selection=False):
		self._file_view.move_cursor_page_down(toggle_selection)
	@run_in_main_thread
	def toggle_selection(self, file_path):
		self._file_view.toggle_selection(file_path)
	@run_in_main_thread
	def focus(self):
		self.setFocus()
	@run_in_main_thread
	def select_all(self):
		self._file_view.selectAll()
	@run_in_main_thread
	def clear_selection(self):
		self._file_view.clearSelection()
	@run_in_main_thread
	def get_selected_files(self):
		return self._file_view.get_selected_files()
	@run_in_main_thread
	def get_file_under_cursor(self):
		return self._file_view.get_file_under_cursor()
	@run_in_main_thread
	def get_path(self):
		result = self._model.rootPath()
		if not result:
			# Displaying "My Computer" - see QFileSystemModel#myComputer()
			return ''
		return normpath(result)
	@run_in_main_thread
	def set_path(self, path, callback=None):
		if callback is None:
			callback = lambda: None
		if is_windows() and _is_documents_and_settings(path):
			# When listing C:\, QFileSystemModel includes the "Documents and
			# Settings" folder. However, it displays no contents when you open
			# that directory. (Actually, no Windows program can display
			# the contents of "C:\Documents and Settings". Explorer says "Access
			# denied", Python gets a PermissionError.) But "C:\Documents and
			# Settings\Michael" does work and displays "C:\Users\Michael".
			# Gracefully handle "C:\Documents and Settings" for the case when
			# the user presses Enter while the cursor is over it:
			path = splitdrive(path)[0] + r'\Users'
		if path == self.get_path():
			# Don't mess up the cursor if we're already in the right location.
			callback()
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
			self._file_view.reset_cursor()
			self.path_changed.emit(self)
			callback()
		connect_once(signal, lambda _: callback_())
		index = self._model_sorted.setRootPath(path)
		self._file_view.setRootIndex(index)
	@run_in_main_thread
	def place_cursor_at(self, file_path):
		self._file_view.place_cursor_at(file_path)
	@run_in_main_thread
	def edit_name(self, file_path):
		self._file_view.edit_name(file_path)
	@run_in_main_thread
	def add_filter(self, filter_):
		self._model_sorted.add_filter(filter_)
	@run_in_main_thread
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

def _is_documents_and_settings(path):
	return splitdrive(normpath(path))[1].lower() == '\\documents and settings'

class MainWindow(QMainWindow):

	pane_added = pyqtSignal(DirectoryPane)
	shown = pyqtSignal()
	closed = pyqtSignal()

	def __init__(self, icon_provider=None):
		super().__init__()
		self.icon_provider = icon_provider
		self.controller = None
		self.panes = []
		self.splitter = Splitter(self)
		self.setCentralWidget(self.splitter)
		self.status_bar = QStatusBar(self)
		self.status_bar_text = QLabel(self.status_bar)
		self.status_bar_text.setOpenExternalLinks(True)
		self.status_bar.addWidget(self.status_bar_text)
		self.status_bar.setSizeGripEnabled(False)
		self.setStatusBar(self.status_bar)
		self.timer = QTimer(self)
		self.timer.timeout.connect(self.clear_status_message)
		self.timer.setSingleShot(True)
	def set_controller(self, controller):
		self.controller = controller
	@run_in_main_thread
	def show_alert(self, text, buttons=OK, default_button=OK):
		with ClearFocusEarly(self):
			msgbox = QMessageBox(self)
			# API users might pass arbitrary objects as text when trying to
			# debug, eg. exception instances. Convert to str(...) to allow for
			# this:
			msgbox.setText(str(text))
			msgbox.setStandardButtons(buttons)
			msgbox.setDefaultButton(default_button)
			if is_mac():
				disable_window_animations_mac(msgbox)
			return msgbox.exec()
	@run_in_main_thread
	def show_file_open_dialog(self, caption, dir_path, filter_text):
		with ClearFocusEarly(self):
			# Let API users pass arbitrary objects by converting with str(...):
			return QFileDialog.getOpenFileName(
				self, str(caption), str(dir_path), str(filter_text)
			)[0]
	@run_in_main_thread
	def show_prompt(self, text, default=''):
		with ClearFocusEarly(self):
			dialog = QInputDialog(self)
			if is_mac():
				disable_window_animations_mac(dialog)
			dialog.setWindowTitle('fman')
			# Let API users pass arbitrary objects by converting with str(...):
			dialog.setLabelText(str(text))
			dialog.setTextEchoMode(QLineEdit.Normal)
			dialog.setTextValue(default)
			result = dialog.exec()
			if result:
				return dialog.textValue(), True
			return '', False
	@run_in_main_thread
	def show_quicksearch(self, get_items, get_tab_completion=None):
		with ClearFocusEarly(self):
			dialog = Quicksearch(self, get_items, get_tab_completion)
			if is_mac():
				disable_window_animations_mac(dialog)
			return dialog.exec()
	@run_in_main_thread
	def show_status_message(self, text, timeout_secs=None):
		self.status_bar_text.setText(text)
		if timeout_secs:
			self.timer.start(int(timeout_secs * 1000))
		else:
			self.timer.stop()
	@run_in_main_thread
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
	def closeEvent(self, _):
		self.closed.emit()

class ClearFocusEarly:
	"""
	At least on Mac, Qt displays dialogs before clearing the main window's
	focus. This leads to an ugly effect: The dialog appears, but a split second
	later, in the background, the cursor in the file view disappears (because
	the widget lost focus). To prevent this from happening, we tell Qt to clear
	the focus *before* launching the dialog. Afterwards, we ensure that the
	original focus is restored.
	"""
	def __init__(self, widget):
		self.widget = widget
		self.focus_widget = None
	def __enter__(self):
		self.focus_widget = self.widget.focusWidget()
		if self.focus_widget:
			self.focus_widget.clearFocus()
	def __exit__(self, *_, **__):
		if self.focus_widget:
			self.focus_widget.setFocus()

class Splitter(QSplitter):
	def createHandle(self):
		result = QSplitterHandle(self.orientation(), self)
		result.installEventFilter(self)
		return result
	def eventFilter(self, splitter_handle, event):
		if event.type() == QEvent.MouseButtonDblClick:
			self._distribute_handles_evenly(splitter_handle.width())
			return True
		return False
	def _distribute_handles_evenly(self, handle_width):
		width_increment = self.width() // self.count()
		for i in range(1, self.count()):
			self.moveSplitter(i * width_increment - handle_width // 2, i)

class SplashScreen(QDialog):
	def __init__(self, parent, app):
		super().__init__(parent, Qt.CustomizeWindowHint | Qt.WindowTitleHint)
		self.app = app
		self.setWindowTitle('fman')

		button_texts = ('A', 'B', 'C')
		button_to_press_i = randint(0, len(button_texts) - 1)
		button_to_press = button_texts[button_to_press_i]

		layout = QVBoxLayout()
		layout.setContentsMargins(20, 20, 20, 20)

		label = QLabel(self)
		p_styles = ['line-height: 115%']
		if is_windows():
			p_styles.extend(['margin-left: 2px', 'text-indent: -2px'])
		p_style = '; '.join(p_styles)
		# Make buy link more enticing on (roughly) every 10th run:
		if randrange(10):
			buy_link_style = ""
		else:
			buy_link_style = " style='color: #00ff00;'"
		label.setText(
			"<center style='line-height: 130%'>"
				"<h2>Welcome to fman!</h2>"
			"</center>"
			"<p style='" + p_style + "'>"
				"To remove this annoying popup, please "
				"<a href='https://fman.io/buy'" + buy_link_style + ">"
					"obtain a license"
				"</a>."
				"<br/>"
				"It only takes a minute and you'll never be bothered again!"
			"</p>"
			"<p style='" + p_style + "'>"
				"To continue without a license for now, press button "
				+ button_to_press + "."
			"</p>"
		)
		label.setOpenExternalLinks(True)
		layout.addWidget(label)

		button_container = QWidget(self)
		button_layout = QHBoxLayout()
		for i, button_text in enumerate(button_texts):
			button = QPushButton(button_text, button_container)
			button.setFocusPolicy(Qt.NoFocus)
			action = self.accept if i == button_to_press_i else self.reject
			button.clicked.connect(action)
			button_layout.addWidget(button)
		button_container.setLayout(button_layout)
		layout.addWidget(button_container)

		self.setLayout(layout)
		self.finished.connect(self._finished)
	def keyPressEvent(self, event):
		if event.matches(QKeySequence.Quit):
			self.app.exit(0)
		else:
			event.ignore()
	def _finished(self, result):
		if result != self.Accepted:
			self.app.exit(0)