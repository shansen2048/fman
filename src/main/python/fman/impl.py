from fman.qt_constants import AscendingOrder, WA_MacShowFocusRect, \
	TextAlignmentRole, AlignVCenter, ClickFocus, Key_Down, Key_Up, \
	Key_Home, Key_End, Key_PageDown, Key_PageUp, Key_Space, Key_Insert, \
	NoModifier, ShiftModifier, ControlModifier, AltModifier, MetaModifier, \
	KeypadModifier, KeyboardModifier, Key_Backspace, Key_Enter, Key_Return, \
	Key_F2, ItemIsEnabled, ItemIsEditable, Key_F6, EditRole
from fman.util.qt import connect_once
from fman.util.system import is_osx
from os import rename
from os.path import abspath, join, pardir, dirname
from PyQt5.QtGui import QKeyEvent, QKeySequence, QDesktopServices
from PyQt5.QtWidgets import QFileSystemModel, QTreeView, QWidget, QSplitter, \
	QLineEdit, QVBoxLayout, QStyle, QStyledItemDelegate
from PyQt5.QtCore import QSortFilterProxyModel, QEvent, QUrl, pyqtSignal, \
	QItemSelectionModel as QISM, QModelIndex

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

class DirectoryPaneController:
	def __init__(self, directory_pane):
		self.directory_pane = directory_pane
	def key_pressed_in_file_view(self, view, event):
		shift = bool(event.modifiers() & ShiftModifier)
		if event.key() == Key_Down:
			if shift:
				view.toggle_current()
			view.move_cursor_down()
		elif event.key() == Key_Up:
			if shift:
				view.toggle_current()
			view.move_cursor_up()
		elif event.key() == Key_Home:
			view.move_cursor_home(self._get_selection_flag(view, shift))
		elif event.key() == Key_End:
			view.move_cursor_end(self._get_selection_flag(view, shift))
		elif event.key() == Key_PageUp:
			view.move_cursor_page_up(self._get_selection_flag(view, shift))
			view.move_cursor_up()
		elif event.key() == Key_PageDown:
			view.move_cursor_page_down(self._get_selection_flag(view, shift))
			view.move_cursor_down()
		elif event.key() == Key_Insert:
			view.toggle_current()
			view.move_cursor_down()
		elif event.key() == Key_Space:
			view.toggle_current()
			if is_osx():
				view.move_cursor_down()
		elif event.key() == Key_Backspace:
			current_dir = self.directory_pane.get_path()
			parent_dir = abspath(join(current_dir, pardir))
			callback = lambda: self.directory_pane.place_cursor_at(current_dir)
			self.directory_pane.set_path(parent_dir, callback)
		elif event.key() in (Key_Enter, Key_Return):
			view.activated.emit(view.currentIndex())
		elif shift and event.key() == Key_F6:
			view.edit(view.currentIndex())
		elif event == QKeySequence.SelectAll:
			view.selectAll()
		else:
			event.ignore()
	def activated(self, model, view, index):
		file_path = model.filePath(index)
		if model.isDir(index):
			view.clearSelection()
			self.directory_pane.set_path(file_path)
		else:
			QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
	def file_renamed(self, model, index, new_name):
		if not new_name:
			return
		src = model.filePath(index)
		dest = join(dirname(src), new_name)
		rename(src, dest)
		self.directory_pane.place_cursor_at(dest)
	def _get_selection_flag(self, view, shift_pressed):
		if shift_pressed:
			if view.selectionModel().isSelected(view.currentIndex()):
				return QISM.Deselect | QISM.Current
			else:
				return QISM.Select | QISM.Current
		else:
			return QISM.NoUpdate

class PathView(QLineEdit):
	def __init__(self):
		super().__init__()
		self.setFocusPolicy(ClickFocus)
		self.setAttribute(WA_MacShowFocusRect, 0)

class TreeViewWithNiceCursorAndSelectionAPI(QTreeView):
	"""
	QTreeView doesn't offer a clean, separated API for manipulating the cursor
	position / selection. This class fixes this. Its implementation works by
	sending fake key events to Qt that have the desired effects of moving the
	cursor / updating the selection. The various `move_cursor_*` methods take
	a `selection_flags` parameter which indicates how the selection should be
	updated as a result of the cursor movement. To get this to work, our
	implementation encodes each selection flag as a modifier key (eg. Shift)
	that is set on the fake key event. Qt's internals then call
	selectionCommand() which decides how the selection should be updated. We
	override this method to decode the modifier keys and make Qt perform the
	desired selection action.
	"""
	_MODIFIERS_TO_SELECTION_FLAGS = [
		(NoModifier, QISM.NoUpdate), (ShiftModifier, QISM.Clear),
		(ControlModifier, QISM.Select), (AltModifier, QISM.Deselect),
		(MetaModifier, QISM.Toggle), (KeypadModifier, QISM.Current)
	]
	def __init__(self):
		super().__init__()
		self.setSelectionMode(self.ContiguousSelection)
	def move_cursor_down(self):
		self._move_cursor(Key_Down)
	def move_cursor_up(self):
		self._move_cursor(Key_Up)
	def move_cursor_page_up(self, selection_flags):
		self._move_cursor(Key_PageUp, selection_flags)
	def move_cursor_page_down(self, selection_flags):
		self._move_cursor(Key_PageDown, selection_flags)
	def move_cursor_home(self, selection_flags):
		self._move_cursor(Key_Home, selection_flags)
	def move_cursor_end(self, selection_flags):
		self._move_cursor(Key_End, selection_flags)
	def toggle_current(self):
		self.selectionModel().select(self.currentIndex(), QISM.Toggle)
	def _move_cursor(self, key, selectionFlags=QISM.NoUpdate):
		modifiers = self._selection_flag_to_modifier(selectionFlags)
		evt = QKeyEvent(QEvent.KeyPress, key, modifiers, '', False, 1)
		super().keyPressEvent(evt)
	def selectionCommand(self, index, event):
		if event and event.type() == QEvent.KeyPress:
			result = self._modifier_to_selection_flag(event.modifiers())
		else:
			result = QISM.NoUpdate
		return QISM.SelectionFlag(result | QISM.Rows)
	def _modifier_to_selection_flag(self, modifiers):
		result = 0
		for modifier, selection_flag in self._MODIFIERS_TO_SELECTION_FLAGS:
			if modifiers & modifier:
				result |= selection_flag
		return QISM.SelectionFlag(result)
	def _selection_flag_to_modifier(self, selection_flags):
		result = 0
		for modifier, selection_flag in self._MODIFIERS_TO_SELECTION_FLAGS:
			if selection_flags & selection_flag:
				result |= modifier
		return KeyboardModifier(result)

class FileListView(TreeViewWithNiceCursorAndSelectionAPI):
	def __init__(self, model, controller):
		super().__init__()
		self.setModel(model)
		self.setItemsExpandable(False)
		self.setRootIsDecorated(False)
		self.setAllColumnsShowFocus(True)
		self.setAnimated(False)
		self.setSortingEnabled(True)
		self.sortByColumn(0, AscendingOrder)
		self.setAttribute(WA_MacShowFocusRect, 0)
		self.setUniformRowHeights(True)
		self.setItemDelegate(FileListItemDelegate())
		self._controller = controller
	def keyPressEvent(self, event):
		self._controller.key_pressed_in_file_view(self, event)
	def drawRow(self, painter, option, index):
		# Even with allColumnsShowFocus set to True, QTreeView::item:focus only
		# styles the first column. Fix this:
		if self.hasFocus() and index.row() == self.currentIndex().row():
			option.state |= QStyle.State_HasFocus
		super().drawRow(painter, option, index)

class FileListItemDelegate(QStyledItemDelegate):
	def eventFilter(self, editor, event):
		if event.type() == QEvent.KeyPress and \
				event.key() in (Key_Enter, Key_Return):
			self.commitData.emit(editor)
			self.closeEditor.emit(editor)
			return True
		return super().eventFilter(editor, event)

class FileSystemModel(QFileSystemModel):

	file_renamed = pyqtSignal(QFileSystemModel, QModelIndex, str)

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
	def flags(self, index):
		return ItemIsEnabled | ItemIsEditable
	def setData(self, index, value, role):
		if role == EditRole:
			self.file_renamed.emit(self, index, value)
			return True
		return super().setData(index, value, role)

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