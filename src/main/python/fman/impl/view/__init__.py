from fman.impl.util.qt import WA_MacShowFocusRect, Key_Home, Key_End, \
	ShiftModifier, Key_Return, Key_Enter, ToolTipRole, connect_once
from fman.impl.view.drag_and_drop import DragAndDrop
from fman.impl.view.move_without_updating_selection import \
	MoveWithoutUpdatingSelection
from fman.impl.view.single_row_mode import SingleRowMode
from fman.impl.view.uniform_row_heights import UniformRowHeights
from math import ceil
from PyQt5.QtCore import QEvent, QItemSelectionModel as QISM, QRect, Qt, \
	pyqtSignal
from PyQt5.QtGui import QPen, QPainter
from PyQt5.QtWidgets import QTableView, QLineEdit, QVBoxLayout, QStyle, \
	QStyledItemDelegate, QProxyStyle, QHeaderView, QToolTip

class ResizeColumnsToContents(QTableView):
	def __init__(self, parent):
		super().__init__(parent)
		self.horizontalHeader().sectionResized.connect(self._on_col_resized)
		self._old_col_widths = None
		self._handle_col_resize = True
	def resizeColumnsToContents(self):
		self._resize_cols_to_contents()
	def resizeEvent(self, event):
		super().resizeEvent(event)
		self._tune_resizeContentsPrecision()
		self._resize_cols_to_contents(self._old_col_widths)
		self._old_col_widths = self._get_column_widths()
	def _tune_resizeContentsPrecision(self):
		"""
		Performance improvement: We call sizeHintForColumn(...). By default,
		this considers 1000 rows. So what Qt does is that it "loads" the 1000
		rows and then computes their size. This can be expensive. We therefore
		reduce 1000 to the number of rows that are actually visible (typically
		~50).
		"""
		num_rows_visible = self._get_num_visible_rows()
		self.horizontalHeader().setResizeContentsPrecision(num_rows_visible)
	def _get_num_visible_rows(self):
		content_height = self.height() - self.horizontalHeader().height()
		# Assumes all rows have the same height:
		return ceil(content_height / self.sizeHintForRow(0))
	def setModel(self, model):
		old_model = self.model()
		if old_model:
			old_model.modelReset.disconnect(self._on_model_reset)
		super().setModel(model)
		model.modelReset.connect(self._on_model_reset)
	def _on_model_reset(self):
		self._old_col_widths = None
	def _resize_cols_to_contents(self, curr_widths=None):
		if self._get_rows_visible_but_not_loaded():
			return
		if curr_widths is None:
			curr_widths = self._get_column_widths()
		min_widths = self._get_min_col_widths()
		width = self._get_width_excl_scrollbar()
		ideal_widths = _get_ideal_column_widths(curr_widths, min_widths, width)
		self._apply_column_widths(ideal_widths)
	def _get_rows_visible_but_not_loaded(self):
		model = self.model()
		return [
			i for i in self._get_visible_row_range()
			if not model.row_is_loaded(i)
		]
	def _get_visible_row_range(self):
		header = self.verticalHeader()
		start = header.logicalIndexAt(0)
		if start == -1:
			start = 0
		stop = header.logicalIndexAt(header.viewport().height()) + 1
		if stop == 0:
			stop = self.model().rowCount()
		return range(start, stop)
	def _get_width_excl_scrollbar(self):
		return self.width() - self._get_vertical_scrollbar_width()
	def _get_vertical_scrollbar_width(self):
		scrollbar = self.verticalScrollBar()
		if scrollbar.isVisible():
			return scrollbar.width()
		required_height = self.viewportSizeHint().height()
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
		header = self.horizontalHeader()
		return [
			max(self.sizeHintForColumn(c), header.sectionSizeHint(c))
			for c in range(self._num_columns)
		]
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

class FileListView(
	SingleRowMode, MoveWithoutUpdatingSelection, DragAndDrop, UniformRowHeights,
	ResizeColumnsToContents
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
		self._urls_being_loaded = []
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
		self.update()
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

def _get_ideal_column_widths(curr_widths, min_widths, available_width):
	if not min_widths:
		raise ValueError(repr(min_widths))
	if len(curr_widths) != len(min_widths):
		curr_widths = [0] * len(min_widths)
	result = list(curr_widths)
	width = sum(curr_widths)
	min_width = sum(min_widths)
	truncated_columns = [
		c for c, (w, m_w) in enumerate(zip(curr_widths, min_widths))
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