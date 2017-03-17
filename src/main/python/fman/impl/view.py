from fman.util.qt import AscendingOrder, WA_MacShowFocusRect, ClickFocus, \
	Key_Down, Key_Up, Key_Home, Key_End, Key_PageDown, Key_PageUp, NoModifier, \
	ShiftModifier, ControlModifier, AltModifier, MetaModifier, KeypadModifier, \
	KeyboardModifier, Key_Enter, Key_Return, Key_Tab, MoveAction, NoButton, \
	CopyAction
from fman.util.system import is_mac
from os.path import normpath
from PyQt5.QtCore import QEvent, QItemSelectionModel as QISM, QDir, Qt, QRect
from PyQt5.QtGui import QKeyEvent, QPen
from PyQt5.QtWidgets import QTreeView, QLineEdit, QVBoxLayout, QStyle, \
	QStyledItemDelegate, QProxyStyle, QAbstractItemView, QDialog, QLabel, \
	QLayout, QListWidget, QListWidgetItem, QFrame, QHBoxLayout

import html

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
	cursor / updating the selection. When updating a selection, the
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

	_IDLE_STATES = (QAbstractItemView.NoState, QAbstractItemView.AnimatingState)

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
		# Double click should not open editor:
		self.setEditTriggers(self.NoEditTriggers)
		self._init_for_drag_and_drop()
	def get_selected_files(self):
		indexes = self.selectionModel().selectedRows(column=0)
		model = self.model()
		return [
			normpath(model.sourceModel().filePath(model.mapToSource(index)))
			for index in indexes
		]
	def get_file_under_cursor(self):
		model = self.model()
		index = self.currentIndex()
		return model.sourceModel().filePath(model.mapToSource(index))
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
		index = self.rootIndex().child(0, 0)
		is_displaying_my_computer = not self.model().sourceModel().rootPath()
		if not index.isValid() and is_displaying_my_computer:
			# This happens when displaying the contents of "My Computer" on
			# Windows. See QFileSystemModel#myComputer().
			self.place_cursor_at(QDir.drives()[0].absolutePath())
		else:
			self.setCurrentIndex(index)
	def _get_index(self, file_path):
		model = self.model()
		return model.mapFromSource(model.sourceModel().index(file_path))
	def _init_for_drag_and_drop(self):
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
				if isinstance(widget, QTreeView):
					# Painting on a QTreeView actually starts painting below the
					# header - at the ` in the below picture:
					#          ___________
					#         |___________|
					#         |`          |
					#         |           |
					#         |___________|
					#
					# The .height() however includes the header's height. This
					# means that the rectangle (w, h) starting at ` would extend
					# too far to the bottom. Correct for this:
					height -= widget.header().height()
				rect = QRect(margin, margin, width, height)
			painter.save()
			pen = QPen(option.palette.light().color())
			pen.setWidth(pen_width)
			painter.setPen(pen)
			painter.drawRect(rect)
			painter.restore()
			return
		super().drawPrimitive(element, option, painter, widget)

class Quicksearch(QDialog):
	def __init__(self, parent, get_items, get_tab_completion=None):
		if get_tab_completion is None:
			get_tab_completion = lambda _: None
		super().__init__(parent, Qt.FramelessWindowHint)
		self.get_items = get_items
		self.get_tab_completion = get_tab_completion
		self._curr_items = []
		self._result = None
		self._init_ui()
	def exec(self):
		self._update_items('')
		self._place_cursor_at_first_item()
		if super().exec():
			return self._result
	def _init_ui(self):
		self._query = LineEdit()
		self._query.keyPressEventFilter = self._on_key_pressed
		self._query.textChanged.connect(self._on_text_changed)
		self._query.returnPressed.connect(self._on_return_pressed)
		self._items = QListWidget()
		self._items.setFocusPolicy(Qt.NoFocus)
		div = lambda widget: self._layout_vertically(Div(), widget)
		query_container = div(div(self._query))
		query_container.setObjectName('query-container')
		items_container = div(self._items)
		items_container.setObjectName('items-container')
		self._layout_vertically(self, query_container, items_container)
		self.layout().setSizeConstraint(QLayout.SetFixedSize)
	def _on_return_pressed(self):
		index = self._items.currentIndex()
		item = self._curr_items[index.row()] if index.isValid() else None
		self._result = self._query.text(), item
		self.accept()
	def _on_key_pressed(self, event):
		if event.key() == Key_Tab:
			index = self._items.currentIndex()
			if index.isValid():
				item = self._curr_items[index.row()]
				completion = self.get_tab_completion(item)
				if completion:
					self._query.setText(completion)
				return True
		if event.key() in (Key_Down, Key_Up, Key_PageDown, Key_PageUp) or \
				is_mac() and event.key() in (Key_Home, Key_End):
			self._items.keyPressEvent(event)
			return True
		return False
	def _on_text_changed(self, text):
		self._update_items(text)
		self._place_cursor_at_first_item()
	def _place_cursor_at_first_item(self):
		model = self._items.model()
		row = 0
		root = self._items.rootIndex()
		while True:
			index = model.index(row, 0, root)
			if index.isValid():
				if not self._items.isIndexHidden(index):
					self._items.setCurrentIndex(index)
					break
			else:
				break
			row += 1
	def _update_items(self, query):
		self._items.clear()
		self._curr_items = self.get_items(query)
		for item in self._curr_items:
			self._add_item(item)
		self._shrink_item_list_to_size()
	def _add_item(self, item):
		widget_item = QListWidgetItem("")
		widget = \
			QuicksearchItem(item.title, item.highlight, item.hint, self._items)
		widget_item.setSizeHint(widget.sizeHint())
		self._items.addItem(widget_item)
		self._items.setItemWidget(widget_item, widget)
	def _shrink_item_list_to_size(self):
		height = self._items.count() * self._items.sizeHintForRow(0)
		self._items.setMaximumHeight(height)
	def _layout_vertically(self, parent, *widgets):
		layout = QVBoxLayout()
		layout.setContentsMargins(0, 0, 0, 0)
		layout.setSpacing(0)
		layout.setAlignment(Qt.AlignTop)
		for widget in widgets:
			layout.addWidget(widget)
		parent.setLayout(layout)
		return parent

class QuicksearchItem(QFrame):
	def __init__(self, title, highlight, hint, parent):
		super().__init__(parent)
		layout = QHBoxLayout()
		layout.setContentsMargins(0, 0, 0, 0)
		layout.setSpacing(0)

		title_widget = QLabel(self._get_title_html(title, highlight), self)
		title_widget.setTextFormat(Qt.RichText)
		title_widget.setObjectName('title')
		layout.addWidget(title_widget)

		if hint:
			hint_widget = QLabel(hint, self)
			hint_widget.setObjectName('hint')
			layout.addWidget(hint_widget)
			layout.insertStretch(1, 2)

		self.setLayout(layout)
	def _get_title_html(self, title, highlight):
		parts = list(map(html.escape, title))
		for i in highlight:
			parts[i] = '<font color="white">' + parts[i] + '</font>'
		return ''.join(parts)

class LineEdit(QLineEdit):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.keyPressEventFilter = None
	def keyPressEvent(self, event):
		filter_ = self.keyPressEventFilter
		if not filter_ or not filter_(event):
			super().keyPressEvent(event)

class Div(QFrame):
	pass