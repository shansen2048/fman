from fman.util.qt import AscendingOrder, WA_MacShowFocusRect, ClickFocus, \
	Key_Down, Key_Up, Key_Home, Key_End, Key_PageDown, Key_PageUp, NoModifier, \
	ShiftModifier, ControlModifier, AltModifier, MetaModifier, KeypadModifier, \
	KeyboardModifier, Key_Enter, Key_Return
from PyQt5.QtCore import QEvent, QItemSelectionModel as QISM
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import QTreeView, QLineEdit, QVBoxLayout, QStyle, \
	QStyledItemDelegate, QProxyStyle, QAbstractItemView

class PathView(QLineEdit):
	def __init__(self, parent=None):
		super().__init__(parent)
		self.setFocusPolicy(ClickFocus)
		self.setAttribute(WA_MacShowFocusRect, 0)
		self.setReadOnly(True)

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
	def __init__(self, parent=None):
		super().__init__(parent)
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
		self.selectionModel().select(
			self.currentIndex(), QISM.Toggle | QISM.Rows
		)
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
	def __init__(self, parent):
		super().__init__(parent)
		self.keyPressEventFilter = None
		self.setItemsExpandable(False)
		self.setRootIsDecorated(False)
		self.setAllColumnsShowFocus(True)
		self.setAnimated(False)
		self.setSortingEnabled(True)
		self.sortByColumn(0, AscendingOrder)
		self.setAttribute(WA_MacShowFocusRect, 0)
		self.setUniformRowHeights(True)
		self.setItemDelegate(FileListItemDelegate())
		self.setSelectionBehavior(QAbstractItemView.SelectRows)
		# Double click should activate the file, not open its editor:
		self.setEditTriggers(self.NoEditTriggers)
	def keyPressEvent(self, event):
		filter_ = self.keyPressEventFilter
		if not filter_ or not filter_(self, event):
			super().keyPressEvent(event)
	def drawRow(self, painter, option, index):
		# Even with allColumnsShowFocus set to True, QTreeView::item:focus only
		# styles the first column. Fix this:
		if self.hasFocus() and index.row() == self.currentIndex().row():
			option.state |= QStyle.State_HasFocus
		super().drawRow(painter, option, index)
	def focusInEvent(self, event):
		if not self.currentIndex().isValid():
			self.reset_cursor()
		super().focusInEvent(event)
	def reset_cursor(self):
		self.setCurrentIndex(self.rootIndex().child(0, 0))

class FileListItemDelegate(QStyledItemDelegate):
	def eventFilter(self, editor, event):
		if event.type() == QEvent.KeyPress and \
				event.key() in (Key_Enter, Key_Return):
			self.commitData.emit(editor)
			self.closeEditor.emit(editor)
			return True
		return super().eventFilter(editor, event)

class Layout(QVBoxLayout):
	def __init__(self, path_view, file_view):
		super().__init__()
		self.addWidget(path_view)
		self.addWidget(file_view)
		self.setContentsMargins(0, 0, 0, 0)
		self.setSpacing(0)

class Style(QProxyStyle):
	def drawPrimitive(self, element, option, painter, widget):
		if element == QStyle.PE_FrameFocusRect:
			# Prevent the ugly dotted border around focused elements on Windows:
			return
		super().drawPrimitive(element, option, painter, widget)