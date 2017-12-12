from fman.impl.util.qt import WA_MacShowFocusRect, ClickFocus, Key_Home, \
	Key_End, ShiftModifier, ControlModifier, AltModifier, MoveAction, \
	NoButton, CopyAction, Key_Return, Key_Enter, ToolTipRole, connect_once
from fman.impl.util.system import is_mac
from PyQt5.QtCore import QEvent, QItemSelectionModel as QISM, QRect, Qt, \
	QItemSelectionModel, pyqtSignal
from PyQt5.QtGui import QPen
from PyQt5.QtWidgets import QTableView, QLineEdit, QVBoxLayout, QStyle, \
	QStyledItemDelegate, QProxyStyle, QAbstractItemView, QHeaderView, QToolTip

class LocationBar(QLineEdit):
	def __init__(self, parent=None):
		super().__init__(parent)
		self.setFocusPolicy(ClickFocus)
		self.setAttribute(WA_MacShowFocusRect, 0)
		self.setReadOnly(True)

class NiceCursorAndSelectionAPIMixin(QTableView):
	def move_cursor_down(self, toggle_selection=False):
		if toggle_selection:
			self._toggle_current_index()
		self._move_cursor(self.MoveDown)
	def move_cursor_up(self, toggle_selection=False):
		if toggle_selection:
			self._toggle_current_index()
		self._move_cursor(self.MoveUp)
	def move_cursor_page_up(self, toggle_selection=False):
		self._move_cursor(self.MovePageUp, toggle_selection)
		self.move_cursor_up()
	def move_cursor_page_down(self, toggle_selection=False):
		self._move_cursor(self.MovePageDown, toggle_selection)
		self.move_cursor_down()
	def move_cursor_home(self, toggle_selection=False):
		self._move_cursor(self.MoveHome, toggle_selection)
	def move_cursor_end(self, toggle_selection=False):
		self._move_cursor(self.MoveEnd, toggle_selection)
	def _toggle_current_index(self):
		index = self.currentIndex()
		if index.isValid():
			self.selectionModel().select(index, QISM.Toggle | QISM.Rows)
	def _move_cursor(self, cursor_action, toggle_selection=False):
		modifiers = self._get_modifiers(cursor_action)
		new_current = self.moveCursor(cursor_action, modifiers)
		old_current = self.currentIndex()
		if new_current != old_current and new_current.isValid():
			self.setCurrentIndex(new_current)
			if toggle_selection:
				rect = QRect(self.visualRect(old_current).center(),
							 self.visualRect(new_current).center())
				command = self._get_toggle_selection_command()
				self.setSelection(rect, command)
		return
	def _get_modifiers(self, cursor_action):
		return Qt.NoModifier
	def _get_toggle_selection_command(self):
		return QItemSelectionModel.Toggle

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
		super().initStyleOption(option, index)
		for item in self._items:
			# Unlike the other methods in this class, we don't call
			# `item.initStyleOption(...)` here, for the following reason:
			# It would have to call `super().initStyleOption(...)`. This is
			# an expensive operation. To avoid having to call it for every
			# `item`, we therefore call it only once - above this for loop -
			# then use `item#adapt_style_option(...)` to make the necessary
			# changes. When 350 files are displayed, this saves about 700ms.
			item.adapt_style_option(option, index)
	def eventFilter(self, editor, event):
		for item in self._items:
			# eventFilter(...) is protected. We can only call it if we
			# reimplemented it ourselves in Python:
			if self._is_python_method(item.eventFilter):
				result = item.eventFilter(editor, event)
				if result:
					return result
		return super().eventFilter(editor, event)
	def helpEvent(self, event, view, option, index):
		for item in self._items:
			result = item.helpEvent(event, view, option, index)
			if result:
				return result
		return super().helpEvent(event, view, option, index)
	def _is_python_method(self, method):
		return hasattr(method, '__func__')

class SingleRowModeMixin(
	# We need to extend NiceCursorAndSelectionAPIMixin because we overwrite
	# some of its methods.
	NiceCursorAndSelectionAPIMixin, CompositeDelegateMixin
):
	def __init__(self, parent=None):
		super().__init__(parent)
		self.setSelectionBehavior(QAbstractItemView.SelectRows)
		self._single_row_delegate = None
		self._would_have_focus = False
	def _get_modifiers(self, cursor_action):
		if cursor_action in (self.MoveHome, self.MoveEnd):
			return Qt.ControlModifier
		return super()._get_modifiers(cursor_action)
	def _get_toggle_selection_command(self):
		return super()._get_toggle_selection_command() \
			   | QItemSelectionModel.Rows
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
			self.move_cursor_home()
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
	def adapt_style_option(self, option, index):
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
		self.key_press_event_filter = lambda source, event: False
		self.setShowGrid(False)
		self.setSortingEnabled(True)
		self.setAttribute(WA_MacShowFocusRect, 0)
		self.horizontalHeader().setStretchLastSection(True)
		self.horizontalHeader().setHighlightSections(False)
		self.horizontalHeader().setDefaultAlignment(Qt.AlignLeft)
		self.setWordWrap(False)
		self.setTabKeyNavigation(False)
		# Double click should not open editor:
		self.setEditTriggers(self.NoEditTriggers)
		self._init_vertical_header()
		self._delegate = FileListItemDelegate()
		self.add_delegate(self._delegate)
		self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
		self.horizontalHeader().sectionResized.connect(self._on_col_resized)
		self._old_col_widths = None
		self._handle_col_resize = True
	def get_selected_files(self):
		indexes = self.selectionModel().selectedRows(column=0)
		return [self._get_url(index) for index in indexes]
	def get_file_under_cursor(self):
		index = self.currentIndex()
		if index.isValid():
			return self._get_url(index)
	def place_cursor_at(self, file_url):
		self.setCurrentIndex(self._get_index(file_url))
	def toggle_selection(self, file_url):
		self.selectionModel().select(
			self._get_index(file_url), QISM.Toggle | QISM.Rows
		)
	def edit_name(self, file_url, selection_start=0, selection_end=None):
		def on_editor_shown(editor):
			set_selection(editor, selection_start, selection_end)
		connect_once(self._delegate.editor_shown, on_editor_shown)
		self.edit(self._get_index(file_url))
	def keyPressEvent(self, event):
		if event.key() in (Key_Return, Key_Enter) \
			and self.state() == self.EditingState:
			# When we're editing - ie. renaming a file - and the user presses
			# Enter, we don't want that key stroke to propagate because it's
			# already "handled" by the editor closing. So "ignore" the event:
			return
		if not self.key_press_event_filter(self, event):
			super().keyPressEvent(event)
	def resizeEvent(self, event):
		super().resizeEvent(event)
		if self._old_col_widths:
			self._resize_cols_to_contents(self._old_col_widths)
		self._old_col_widths = self._get_column_widths()
	def resizeColumnsToContents(self):
		self._resize_cols_to_contents()
	def setModel(self, model):
		old_model = self.model()
		if old_model:
			old_model.modelReset.disconnect(self._on_model_reset)
		super().setModel(model)
		model.modelReset.connect(self._on_model_reset)
	def _on_model_reset(self):
		self._old_col_widths = None
	def _resize_cols_to_contents(self, curr_widths=None):
		if curr_widths is None:
			curr_widths = self._get_column_widths()
		min_widths = self._get_min_col_widths()
		width = self._get_width_excl_scrollbar()
		ideal_widths = _get_ideal_column_widths(curr_widths, min_widths, width)
		self._apply_column_widths(ideal_widths)
	def _get_width_excl_scrollbar(self):
		return self.width() - self._get_vertical_scrollbar_width()
	def _get_vertical_scrollbar_width(self):
		scrollbar = self.verticalScrollBar()
		if scrollbar.isVisible():
			return scrollbar.width()
		# This assumes that all rows have the same height:
		required_height = self.horizontalHeader().height() + \
						  self.rowHeight(0) * self.model().rowCount()
		will_scrollbar_be_visible = required_height > self.height()
		if will_scrollbar_be_visible:
			# This for instance happens when fman is just starting up. In this
			# case, scrollbar.isVisible() is False even though it is visible on
			# the screen. One theory that could explain this is that in the
			# initial paint event, Qt gives us the entire viewport to paint on.
			# It then realizes that we used more than the available height and
			# draws the vertical scrollbar on top of the viewport - without
			# setting isVisible() to True. But this is just a theory.
			return scrollbar.sizeHint().width()
		return 0
	def _get_column_widths(self):
		return [self.columnWidth(i) for i in range(self._num_columns)]
	def _get_min_col_widths(self):
		return [self.sizeHintForColumn(c) for c in range(self._num_columns)]
	def _apply_column_widths(self, widths):
		for col, width in enumerate(widths):
			self.setColumnWidth(col, width)
	@property
	def _num_columns(self):
		return self.horizontalHeader().count()
	def _on_col_resized(self, col, old_size, size):
		if old_size == size:
			return
		# Prevent infinite recursion:
		if not self._handle_col_resize:
			return
		self._handle_col_resize = False
		try:
			widths = self._get_column_widths()
			widths[col] = old_size
			min_widths = self._get_min_col_widths()
			width = self._get_width_excl_scrollbar()
			new_widths = _resize_column(col, size, widths, min_widths, width)
			self._apply_column_widths(new_widths)
		finally:
			self._handle_col_resize = True
	def _init_vertical_header(self):
		# The vertical header is what would in Excel be displayed as the row
		# numbers 0, 1, ... to the left of the table. Qt displays it by default.
		vertical_header = self.verticalHeader()
		vertical_header.hide()
		# Don't let the vertical header determine the row height:
		vertical_header.setStyleSheet("QHeaderView::section { padding: 0px; }")
		vertical_header.setMinimumSectionSize(0)
		vertical_header.setSectionResizeMode(QHeaderView.ResizeToContents)
	def _get_index(self, file_url):
		model = self.model()
		return model.mapFromSource(model.sourceModel().find(file_url))
	def _get_url(self, index):
		model = self.model()
		return model.sourceModel().url(model.mapToSource(index))

def set_selection(qlineedit, selection_start, selection_end=None):
	"""
	Set the selection and/or cursor on the given QLineEdit. The indices
	`selection_start` and `selection_end` identify the respective "gap" between
	characters, where the cursor can be placed. If you want to only set the
	cursor position without selecting anything, use
	selection_start = selection_end. The default of selection_end=None indicates
	that everything from selection_start until the end of the text is to be
	selected.
	"""
	text_len = len(qlineedit.text())
	if selection_end is None:
		selection_end = text_len
	cursor_pos = selection_start
	if selection_start == selection_end:
		qlineedit.setCursorPosition(cursor_pos)
	else:
		selection_len = selection_end - selection_start
		qlineedit.setSelection(cursor_pos, selection_len)

def _get_ideal_column_widths(widths, min_widths, available_width):
	if len(widths) != len(min_widths):
		raise ValueError('len(%r) != len(%r)!' % (widths, min_widths))
	if not widths:
		return []
	result = list(widths)
	width = sum(widths)
	min_width = sum(min_widths)
	truncated_columns = [
		c for c, (w, m_w) in enumerate(zip(widths, min_widths))
		if w < m_w
	]
	if truncated_columns:
		if min_width <= available_width:
			# Simply enlarge the truncated columns.
			for c in truncated_columns:
				result[c] = min_widths[c]
			width = sum(result)
	if width > available_width:
		trim_required = width - available_width
		trimmable_cols = [
			c for c, (w, m_w) in enumerate(zip(result, min_widths))
			if w > m_w
		]
		trimmable_widths = [result[c] - min_widths[c] for c in trimmable_cols]
		trimmable_width = sum(trimmable_widths)
		to_trim = min(trim_required, trimmable_width)
		col_trims = _distribute_evenly(to_trim, trimmable_widths)
		for c, trim in zip(trimmable_cols, col_trims):
			result[c] -= trim
		trim_required -= to_trim
		if trim_required > 0:
			col_trims = _distribute_exponentially(trim_required, result)
			for c, trim in enumerate(col_trims):
				result[c] -= trim
	elif width < available_width:
		result[0] += available_width - width
	last_col_excess = result[-1] - min_widths[-1]
	if last_col_excess > 0:
		result[-1] -= last_col_excess
		result[0] += last_col_excess
	return result

def _distribute_evenly(width, proportions):
	total = sum(proportions)
	if not total:
		return [0] * len(proportions)
	return [int(p / total * width) for p in proportions]

def _distribute_exponentially(width, proportions):
	total = sum(p * p for p in proportions)
	if not total:
		return [0] * len(proportions)
	return [int(p * p / total * width) for p in proportions]

def _resize_column(col, new_size, widths, min_widths, available_width):
	old_size = widths[col]
	result = list(widths)
	result[col] = new_size
	if old_size <= 0 or col == len(widths) - 1:
		return result
	delta = new_size - old_size
	if delta > 0:
		for c in range(col + 1, len(widths)):
			width = widths[c]
			trimmable = width - min_widths[c]
			if trimmable > 0:
				trim = min(delta, trimmable)
				result[c] = width - trim
				delta -= trim
				if not delta:
					break
	else:
		next_col = col + 1
		if sum(result) < available_width:
			result[next_col] -= delta
	to_distribute = available_width - sum(result)
	if to_distribute > 0:
		for c, (w, m_w) in enumerate(zip(widths, min_widths)):
			room = m_w - w
			if room > 0:
				expand = min(to_distribute, room)
				result[c] += expand
				to_distribute -= expand
				if not to_distribute:
					break
	return result

class FileListItemDelegate(QStyledItemDelegate):

	editor_shown = pyqtSignal(QLineEdit)

	def eventFilter(self, editor, event):
		if not editor:
			# Are required to return True iff "editor is a valid QWidget and the
			# given event is handled". No editor means not valid:
			return False
		if event.type() == QEvent.Show:
			self.editor_shown.emit(editor)
		elif event.type() == QEvent.KeyPress:
			# On Mac, the default implementation of Qt jumps to the first/last
			# list item when the user presses Home/End while editing a file. We
			# want to jump to the start/end of the text in the editor instead:
			key = event.key()
			if key in (Key_Home, Key_End):
				update_cursor = editor.home if key == Key_Home else editor.end
				update_cursor(bool(event.modifiers() & ShiftModifier))
				return True
		return False
	def adapt_style_option(self, option, index):
		# We want to be able to style the first and last columns with QSS.
		# However, unlike QTreeView::item, QTableView::item has no :first or
		# :last selectors. We work around this by setting the fake
		# :has-children and :open selectors:
		if index.column() == 0:
			option.state |= QStyle.State_Children
		if index.column() == index.model().columnCount() - 1:
			option.state |= QStyle.State_Open
	def helpEvent(self, event, view, option, index):
		if not event or not view:
			# Mimic super implementation.
			return False
		if event.type() == QEvent.ToolTip:
			text_width = self.sizeHint(view.viewOptions(), index).width()
			column_width = view.columnWidth(index.column())
			if text_width > column_width:
				# Show the tooltip.
				tooltip_text = index.data(ToolTipRole)
			else:
				# Hide the tooltip.
				tooltip_text = ''
			QToolTip.showText(event.globalPos(), tooltip_text, view)
			return True
		return super().helpEvent(event, view, option, index)

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