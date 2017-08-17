from fman.util.qt import WA_MacShowFocusRect, ClickFocus, Key_Down, Key_Up, \
	Key_Home, Key_End, Key_PageDown, Key_PageUp, NoModifier, ShiftModifier, \
	ControlModifier, AltModifier, MetaModifier, KeypadModifier, \
	KeyboardModifier, GroupSwitchModifier, MoveAction, NoButton, CopyAction
from fman.util.system import is_mac
from os.path import normpath
from PyQt5.QtCore import QEvent, QItemSelectionModel as QISM, QDir, QRect, Qt
from PyQt5.QtGui import QKeyEvent, QPen
from PyQt5.QtWidgets import QTableView, QLineEdit, QVBoxLayout, QStyle, \
	QStyledItemDelegate, QProxyStyle, QAbstractItemView, QHeaderView

class PathView(QLineEdit):
	def __init__(self, parent=None):
		super().__init__(parent)
		self.setFocusPolicy(ClickFocus)
		self.setAttribute(WA_MacShowFocusRect, 0)
		self.setReadOnly(True)

class NiceCursorAndSelectionAPIMixin(QTableView):
	"""
	QTableView doesn't offer a clean, separated API for manipulating the cursor
	position / selection. This class fixes this. Its implementation works by
	sending fake key events to Qt that have the desired effects of moving the
	cursor / updating the selection. When updating a selection, the
	implementation encodes each selection flag as a modifier key (eg. Shift)
	that is set on the fake key event. Qt's internals then call
	selectionCommand() which decides how the selection should be updated. We
	override this method to decode the modifier keys and make Qt perform the
	desired selection action.
	"""
	_MODIFIERS_TO_SELECTION_FLAGS = [
		(NoModifier, QISM.NoUpdate), (ShiftModifier, QISM.Clear),
		(GroupSwitchModifier, QISM.Select), (AltModifier, QISM.Deselect),
		(MetaModifier, QISM.Toggle), (KeypadModifier, QISM.Current)
	]
	def move_cursor_down(self, toggle_selection=False):
		self._move_cursor(Key_Down, toggle_selection)
	def move_cursor_up(self, toggle_selection=False):
		self._move_cursor(Key_Up, toggle_selection)
	def move_cursor_page_up(self, toggle_selection=False):
		self._move_cursor(Key_PageUp, toggle_selection)
	def move_cursor_page_down(self, toggle_selection=False):
		self._move_cursor(Key_PageDown, toggle_selection)
	def move_cursor_home(self, toggle_selection=False):
		self._move_cursor(Key_Home, toggle_selection)
	def move_cursor_end(self, toggle_selection=False):
		self._move_cursor(Key_End, toggle_selection)
	def _move_cursor(self, key, toggle_selection=False):
		selection_flags = self._get_selection_flags(toggle_selection)
		modifiers = self._selection_flag_to_modifier(selection_flags)
		if key in (Key_Home, Key_End):
			# Qt only moves to the last row for these keys when Ctrl is pressed:
			modifiers |= ControlModifier
		evt = QKeyEvent(QEvent.KeyPress, key, modifiers, '', False, 1)
		super().keyPressEvent(evt)
	def _get_selection_flags(self, toggle_selection):
		if toggle_selection:
			if self.selectionModel().isSelected(self.currentIndex()):
				return QISM.Deselect | QISM.Current
			else:
				return QISM.Select | QISM.Current
		else:
			return QISM.NoUpdate
	def selectionCommand(self, index, event):
		if event and event.type() == QEvent.KeyPress:
			return self._modifier_to_selection_flag(event.modifiers())
		return super().selectionCommand(index, event)
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

class CompositeDelegateMixin(QTableView):
	""" Let a QTableView have multiple ItemDelegates. """
	def __init__(self, parent=None):
		super().__init__(parent)
		self._composite_delegate = CompositeItemDelegate(self)
		self.setItemDelegate(self._composite_delegate)
	def add_delegate(self, delegate):
		self._composite_delegate.add(delegate)
	def remove_delegate(self, delegate):
		self._composite_delegate.remove(delegate)

class CompositeItemDelegate(QStyledItemDelegate):
	def __init__(self, parent=None):
		super().__init__(parent)
		self._items = []
	def add(self, item):
		self._items.append(item)
	def remove(self, item):
		self._items.remove(item)
	def initStyleOption(self, option, index):
		for item in self._items:
			item.initStyleOption(option, index)
	def eventFilter(self, editor, event):
		for item in self._items:
			# eventFilter(...) is protected. We can only call it if we
			# reimplemented it ourselves in Python:
			if self._is_python_method(item.eventFilter):
				result = item.eventFilter(editor, event)
				if result:
					return result
		return super().eventFilter(editor, event)
	def _is_python_method(self, method):
		return hasattr(method, '__func__')

class SingleRowModeMixin(
	# We need to extend NiceCursorAndSelectionAPIMixin because we overwrite
	# selectionCommand(...). If we didn't extend NCASAPIM here, our
	# super().selectionCommand(...) would call the implementation in QTableView,
	# not NCASAPIM's.
	NiceCursorAndSelectionAPIMixin, CompositeDelegateMixin
):
	def __init__(self, parent=None):
		super().__init__(parent)
		self.setSelectionBehavior(QAbstractItemView.SelectRows)
		self._single_row_delegate = None
		self._would_have_focus = False
	def moveCursor(self, cursorAction, modifiers):
		result = super().moveCursor(cursorAction, modifiers)
		if result.isValid() and result.column() != 0:
			result = result.sibling(result.row(), 0)
		return result
	def selectionCommand(self, index, event):
		return super().selectionCommand(index, event) | QISM.Rows
	def setSelectionModel(self, selectionModel):
		if self.selectionModel():
			self.selectionModel().currentRowChanged.disconnect(
				self._current_row_changed
			)
			assert self._single_row_delegate
			self.remove_delegate(self._single_row_delegate)
		super().setSelectionModel(selectionModel)
		selectionModel.currentRowChanged.connect(self._current_row_changed)
		self._single_row_delegate = SingleRowModeDelegate(self)
		self.add_delegate(self._single_row_delegate)
	def focusInEvent(self, event):
		if not self.currentIndex().isValid():
			self.reset_cursor()
		super().focusInEvent(event)
		self._would_have_focus = True
	def focusOutEvent(self, event):
		super().focusOutEvent(event)
		self._would_have_focus = event.reason() in (
			Qt.ActiveWindowFocusReason, Qt.PopupFocusReason,
			Qt.MenuBarFocusReason
		)
	def _current_row_changed(self, current, previous):
		# When the cursor moves, Qt only repaints the cell that was left and
		# the cell that was entered. But because we are highlighting the entire
		# row the cursor is on, we need to tell Qt to also update the remaining
		# cells of the same row.
		self._update_entire_row(current)
		self._update_entire_row(previous)
	def _update_entire_row(self, index):
		for column in range(self.model().columnCount(self.rootIndex())):
			self.update(index.sibling(index.row(), column))

class SingleRowModeDelegate(QStyledItemDelegate):
	def __init__(self, view):
		super().__init__(view)
		self._view = view
	def initStyleOption(self, option, index):
		super().initStyleOption(option, index)
		if self._should_draw_cursor(index):
			option.state |= QStyle.State_HasFocus
	def _should_draw_cursor(self, index):
		# Highlight the entire row (rather than just the first column) on focus.
		view = self._view
		if index.row() != view.currentIndex().row():
			return False
		# QTableView::item:focus is only applied when the window has focus. This
		# means that the cursor disappears when the window is in the background
		# (or behind a modal). This leads to non-pleasant flickering effects.
		# So we always highlight the cursor even when the window doesn't have
		# focus:
		return view.hasFocus() or \
			   (not view.isActiveWindow() and view._would_have_focus)

class MovementWithoutUpdatingSelectionMixin(QTableView):
	def __init__(self, parent=None):
		super().__init__(parent)
		self.setSelectionMode(self.NoSelection)
	def selectAll(self):
		self.setSelectionMode(self.ContiguousSelection)
		super().selectAll()
		self.setSelectionMode(self.NoSelection)

class DragAndDropMixin(QTableView):

	_IDLE_STATES = (QAbstractItemView.NoState, QAbstractItemView.AnimatingState)

	def __init__(self, parent=None):
		super().__init__(parent)
		self._dragged_index = None
		self.setDragEnabled(True)
		self.setDragDropMode(self.DragDrop)
		self.setDefaultDropAction(MoveAction)
		self.setDropIndicatorShown(True)
		self.setAcceptDrops(True)
		# Consider:
		#   A/
		#   B/
		# Drag A/ downwards. With dragDropOverwriteMode = False, as you leave A/
		# but before you reach B/, Qt draws a horizontal line between A/ and B/,
		# presumably to let you drag items to between rows. This may make sense
		# for other widgets, but we don't want it. We therefore set
		# dragDropOverwriteMode to True:
		self.setDragDropOverwriteMode(True)
	def mouseMoveEvent(self, event):
		if event.buttons() != NoButton and self.state() in self._IDLE_STATES:
			self._dragged_index = self.indexAt(event.pos())
			if self._dragged_index.isValid():
				# Qt's default implementation only starts dragging when there
				# are selected items. We also want to start dragging when there
				# aren't (because in this case we drag the focus item):
				self.setState(self.DraggingState)
				# startDrag(...) below now initiates drag and drop.
				return
		else:
			super().mouseMoveEvent(event)
	def startDrag(self, supportedActions):
		if not self._dragged_index or not self._dragged_index.isValid():
			return
		if self._dragged_index in self.selectedIndexes():
			super().startDrag(supportedActions)
		else:
			# The default implementation of Qt only supports dragging the
			# currently selected item(s). We therefore briefly need to "select"
			# the items we wish to drag. This has the (unintended) side-effect
			# that the dragged items are also rendered as being selected.
			selection = self.selectionModel().selection()
			current = self.selectionModel().currentIndex()
			try:
				self.selectionModel().clear()
				# When dragging items that have actually been selected by the
				# user, the cursor is on one of the selected items (because the
				# user clicked on it when initiating the drag). Mimic the same
				# behaviour for consistency:
				self.setCurrentIndex(self._dragged_index)
				self.selectionModel().select(
					self._dragged_index, QISM.ClearAndSelect | QISM.Rows
				)
				super().startDrag(supportedActions)
			finally:
				self.selectionModel().select(selection, QISM.ClearAndSelect)
				self.selectionModel().setCurrentIndex(current, QISM.NoUpdate)
	def dropEvent(self, event):
		copy_modifier = AltModifier if is_mac() else ControlModifier
		do_copy = event.keyboardModifiers() & copy_modifier
		action = CopyAction if do_copy else MoveAction
		event.setDropAction(action)
		super().dropEvent(event)

class FileListView(
	SingleRowModeMixin, MovementWithoutUpdatingSelectionMixin, DragAndDropMixin
):
	def __init__(self, parent):
		super().__init__(parent)
		self.keyPressEventFilter = None
		self.setShowGrid(False)
		self.setSortingEnabled(True)
		self.setAttribute(WA_MacShowFocusRect, 0)
		self.horizontalHeader().setStretchLastSection(True)
		self.horizontalHeader().setHighlightSections(False)
		self.setWordWrap(False)
		self.setTabKeyNavigation(False)
		# Double click should not open editor:
		self.setEditTriggers(self.NoEditTriggers)
		self._init_vertical_header()
		self.add_delegate(FileListItemDelegate())
	def get_selected_files(self):
		indexes = self.selectionModel().selectedRows(column=0)
		return [normpath(self._get_path(index)) for index in indexes]
	def get_file_under_cursor(self):
		return self._get_path(self.currentIndex())
	def place_cursor_at(self, file_path):
		self.setCurrentIndex(self._get_index(file_path))
	def toggle_selection(self, file_path):
		self.selectionModel().select(
			self._get_index(file_path), QISM.Toggle | QISM.Rows
		)
	def edit_name(self, file_path):
		self.edit(self._get_index(file_path))
	def keyPressEvent(self, event):
		filter_ = self.keyPressEventFilter
		if not filter_ or not filter_(self, event):
			super().keyPressEvent(event)
	def _init_vertical_header(self):
		# The vertical header is what would in Excel be displayed as the row
		# numbers 0, 1, ... to the left of the table. Qt displays it by default.
		vertical_header = self.verticalHeader()
		vertical_header.hide()
		# Don't let the vertical header determine the row height:
		vertical_header.setStyleSheet("QHeaderView::section { padding: 0px; }")
		vertical_header.setMinimumSectionSize(0)
		vertical_header.setSectionResizeMode(QHeaderView.ResizeToContents)
	def _get_index(self, file_path):
		model = self.model()
		return model.mapFromSource(model.sourceModel().index(file_path))
	def _get_path(self, index):
		model = self.model()
		return model.sourceModel().filePath(model.mapToSource(index))

class FileListItemDelegate(QStyledItemDelegate):
	def eventFilter(self, editor, event):
		if not editor:
			# Are required to return True iff "editor is a valid QWidget and the
			# given event is handled". No editor means not valid:
			return False
		if event.type() == QEvent.KeyPress:
			# On Mac, the default implementation of Qt jumps to the first/last
			# list item when the user presses Home/End while editing a file. We
			# want to jump to the start/end of the text in the editor instead:
			key = event.key()
			if key in (Key_Home, Key_End):
				update_cursor = editor.home if key == Key_Home else editor.end
				update_cursor(bool(event.modifiers() & ShiftModifier))
				return True
		return False
	def initStyleOption(self, option, index):
		super().initStyleOption(option, index)
		if index.column() == 0:
			# We want to be able to style the first column via QSS. However,
			# unlike QTreeView::item, QTableView::item has no :first selector.
			# We work around this by setting the fake :has-children selector on
			# the item when it is in the first column:
			option.state |= QStyle.State_Children

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
		if element == QStyle.PE_IndicatorItemViewItemDrop:
			# This element draws the drop indicator during drag and drop
			# operations, ie. the rectangle around the drop target. In the case
			# of a tree view for instance, the drop target could be the tree
			# item that is under the mouse cursor while dragging.
			rect = option.rect
			pen_width = 2
			if not rect.height():
				# This happens in two cases:
				#  1) Qt allows dropping items "between" rows. The drop
				#     indicator in this case is a horizontal line between the
				#     two rows, indicated by a rect of height 0.
				#     (DropIndicatorPosition "AboveItem" and "BelowItem")
				#  2) When the mouse cursor isn't over any item
				#     (DropIndicatorPosition "OnViewport")
				# In both cases, we want to draw a rectangle around the entire
				# viewport:
				margin = pen_width // 2
				width = widget.width() - margin * 2
				height = widget.height() - margin * 2
				if isinstance(widget, QTableView):
					# Painting on a QTableView actually starts painting below
					# the header - at the ` in the below picture:
					#          ___________
					#         |___________|
					#         |`          |
					#         |           |
					#         |___________|
					#
					# The .height() however includes the header's height. This
					# means that the rectangle (w, h) starting at ` would extend
					# too far to the bottom. Correct for this:
					height -= widget.horizontalHeader().height()
				rect = QRect(margin, margin, width, height)
			painter.save()
			pen = QPen(option.palette.light().color())
			pen.setWidth(pen_width)
			painter.setPen(pen)
			painter.drawRect(rect)
			painter.restore()
			return
		super().drawPrimitive(element, option, painter, widget)