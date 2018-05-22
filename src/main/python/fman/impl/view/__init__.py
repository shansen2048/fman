from fman.impl.util.qt import WA_MacShowFocusRect, Key_Home, Key_End, \
	ShiftModifier, Key_Return, Key_Enter, ToolTipRole, connect_once
from fman.impl.view.drag_and_drop import DragAndDrop
from fman.impl.view.move_without_updating_selection import \
	MoveWithoutUpdatingSelection
from fman.impl.view.resize_cols_to_contents import ResizeColumnsToContents
from fman.impl.view.single_row_mode import SingleRowMode
from fman.impl.view.uniform_row_heights import UniformRowHeights
from PyQt5.QtCore import QEvent, QItemSelectionModel as QISM, QRect, Qt, \
	pyqtSignal
from PyQt5.QtGui import QPen, QContextMenuEvent, QKeySequence
from PyQt5.QtWidgets import QTableView, QLineEdit, QVBoxLayout, QStyle, \
	QStyledItemDelegate, QProxyStyle, QHeaderView, QToolTip, QMenu, QAction

class FileListView(
	SingleRowMode, MoveWithoutUpdatingSelection, DragAndDrop,
	ResizeColumnsToContents
):
	def __init__(self, parent, get_context_menu):
		super().__init__(parent)
		self._get_context_menu = get_context_menu
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
		self.setContextMenuPolicy(Qt.DefaultContextMenu)
		self._urls_being_loaded = []
	def contextMenuEvent(self, event):
		index = self.indexAt(event.pos())
		updated_selection = False
		if index.isValid():
			file_under_mouse = self.model().url(index)
			if event.reason() == QContextMenuEvent.Mouse:
				# Our context menu implementation simply calls plugin commands.
				# Many commands act on the selected files, or the file under the
				# cursor if no file is selected. This lets the user press Insert
				# to select files and move the cursor down, then perform actions
				# on the selected files above - and not(!) the file under the
				# cursor.
				# Consider what happens in the above scenario when the user
				# launches the context menu on the file under the cursor with
				# the mouse. The expectation would be for this to act on the
				# file under the cursor (because it was just selected with the
				# mouse). But without special treatment of this case, our
				# implementation would call the command on the selected files,
				# as if it had been invoked via the keyboard.
				# To solve this, we reset the selection to the file that was
				# clicked on when the user opens the context menu by mouse. This
				# way, the command sees (and naturally acts on) the correct
				# "selected" file. This behaviour exactly mimics that of Total
				# Commander.
				model = self.selectionModel()
				if not model.isSelected(index):
					model.select(index, QISM.ClearAndSelect | QISM.Rows)
					updated_selection = True
		else:
			file_under_mouse = None
		menu = QMenu(self)
		for caption, shortcut, callback in self._get_context_menu(
			event, file_under_mouse
		):
			if caption == '-':
				menu.addSeparator()
			else:
				action = QAction(caption, self)
				# Need `c=callback` to create one lambda per loop:
				action.triggered.connect(lambda _, c=callback: c())
				if shortcut:
					action.setShortcut(QKeySequence(shortcut))
				menu.addAction(action)
		pos = event.globalPos()
		if event.reason() != QContextMenuEvent.Mouse:
			# For some reason, event.globalPos() does not take the header into
			# account when not caused by mouse. Correct for this:
			pos.setY(pos.y() + self.horizontalHeader().height())
		menu.exec(pos)
		if updated_selection:
			self.clearSelection()
	def get_selected_files(self):
		indexes = self.selectionModel().selectedRows(column=0)
		return [self.model().url(index) for index in indexes]
	def get_file_under_cursor(self):
		index = self.currentIndex()
		if index.isValid():
			return self.model().url(index)
	def place_cursor_at(self, file_url):
		self.setCurrentIndex(self.model().find(file_url))
	def toggle_selection(self, file_url):
		self.selectionModel().select(
			self.model().find(file_url), QISM.Toggle | QISM.Rows
		)
	def edit_name(self, file_url, selection_start=0, selection_end=None):
		def on_editor_shown(editor):
			set_selection(editor, selection_start, selection_end)
		connect_once(self._delegate.editor_shown, on_editor_shown)
		self.edit(self.model().find(file_url))
	def keyPressEvent(self, event):
		if event.key() in (Key_Return, Key_Enter) \
			and self.state() == self.EditingState:
			# When we're editing - ie. renaming a file - and the user presses
			# Enter, we don't want that key stroke to propagate because it's
			# already "handled" by the editor closing. So "ignore" the event:
			return
		if not self.key_press_event_filter(self, event):
			super().keyPressEvent(event)
	def setModel(self, model):
		old_model = self.model()
		if old_model:
			old_model.sort_order_changed.disconnect(self._on_sort_order_changed)
		super().setModel(model)
		model.sort_order_changed.connect(self._on_sort_order_changed)
	def _on_sort_order_changed(self, column, order):
		self.sortByColumn(column, order)
	def paintEvent(self, event):
		missing_rows, missing_urls = self._get_rows_to_load()
		if missing_rows:
			self._urls_being_loaded.extend(missing_urls)
			def callback(location=self.model().get_location()):
				self._on_rows_loaded(location, missing_urls)
			self.model().load_rows(missing_rows, callback=callback)
		super().paintEvent(event)
	def _get_rows_to_load(self):
		rows = self._get_rows_visible_but_not_loaded()
		urls = [
			self.model().url(self.model().index(row, 0))
			for row in rows
		]
		for url in self._urls_being_loaded:
			try:
				i = urls.index(url)
			except ValueError:
				continue
			del rows[i]
			del urls[i]
		return rows, urls
	def _on_rows_loaded(self, location, urls):
		if location != self.model().get_location():
			return
		for url in urls:
			try:
				self._urls_being_loaded.remove(url)
			except ValueError:
				pass
	def _on_model_reset(self):
		self._urls_being_loaded = []
		super()._on_model_reset()
	def _init_vertical_header(self):
		# The vertical header is what would in Excel be displayed as the row
		# numbers 0, 1, ... to the left of the table. Qt displays it by default.
		vertical_header = self.verticalHeader()
		vertical_header.hide()
		# Don't let the vertical header determine the row height:
		vertical_header.setStyleSheet("QHeaderView::section { padding: 0px; }")
		vertical_header.setMinimumSectionSize(0)
		vertical_header.setSectionResizeMode(QHeaderView.ResizeToContents)

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
	def createEditor(self, parent, option, index):
		result = super().createEditor(parent, option, index)
		result.setObjectName('editor')
		return result

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