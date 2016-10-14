from fman.util.qt import AscendingOrder, WA_MacShowFocusRect, ClickFocus, \
	Key_Down, Key_Up, Key_Home, Key_End, Key_PageDown, Key_PageUp, NoModifier, \
	ShiftModifier, ControlModifier, AltModifier, MetaModifier, KeypadModifier, \
	KeyboardModifier, Key_Enter, Key_Return, Key_Tab
from fman.util.system import is_mac
from os.path import normpath
from PyQt5.QtCore import QEvent, QItemSelectionModel as QISM, QDir, Qt
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import QTreeView, QLineEdit, QVBoxLayout, QStyle, \
	QStyledItemDelegate, QProxyStyle, QAbstractItemView, QDialog, QLabel, \
	QLayout, QListWidget, QListWidgetItem, QFrame

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

class QuickSearch(QDialog):
	def __init__(self, parent, get_suggestions, get_tab_completion):
		super().__init__(parent, Qt.FramelessWindowHint)
		self.get_suggestions = get_suggestions
		self.get_tab_completion = get_tab_completion
		self._curr_suggestions = []
		self._result = None
		self._init_ui()
	def exec(self):
		self._update_suggestions('')
		self._place_cursor_at_first_suggestion()
		if super().exec():
			return self._result
	def _init_ui(self):
		self._query = LineEdit()
		self._query.keyPressEventFilter = self._on_key_pressed
		self._query.textChanged.connect(self._on_text_changed)
		self._query.returnPressed.connect(self._on_return_pressed)
		self._suggestions = QListWidget()
		self._suggestions.setFocusPolicy(Qt.NoFocus)
		div = lambda widget: self._layout_vertically(Div(), widget)
		query_container = div(div(self._query))
		query_container.setObjectName('query-container')
		suggestions_container = div(self._suggestions)
		suggestions_container.setObjectName('suggestions-container')
		self._layout_vertically(self, query_container, suggestions_container)
		self.layout().setSizeConstraint(QLayout.SetFixedSize)
	def _add_suggestion(self, suggestion, pos=None):
		if pos is None:
			pos = self._suggestions.count()
		widget_item = QListWidgetItem("")
		widget = QuickSearchResult(suggestion, self._suggestions)
		widget_item.setSizeHint(widget.sizeHint())
		self._suggestions.insertItem(pos, widget_item)
		self._suggestions.setItemWidget(widget_item, widget)
	def _on_return_pressed(self):
		index = self._suggestions.currentIndex()
		suggestion = \
			self._curr_suggestions[index.row()] if index.isValid() else None
		self._result = self._query.text(), suggestion
		self.accept()
	def _on_key_pressed(self, event):
		if event.key() == Key_Tab:
			index = self._suggestions.currentIndex()
			if index.isValid():
				suggestion = self._curr_suggestions[index.row()]
				self._query.setText(self.get_tab_completion(suggestion))
				return True
		if event.key() in (Key_Down, Key_Up, Key_PageDown, Key_PageUp) or \
				is_mac() and event.key() in (Key_Home, Key_End):
			self._suggestions.keyPressEvent(event)
			return True
		return False
	def _on_text_changed(self, text):
		self._update_suggestions(text)
		self._place_cursor_at_first_suggestion()
	def _place_cursor_at_first_suggestion(self):
		model = self._suggestions.model()
		row = 0
		root = self._suggestions.rootIndex()
		while True:
			index = model.index(row, 0, root)
			if index.isValid():
				if not self._suggestions.isIndexHidden(index):
					self._suggestions.setCurrentIndex(index)
					break
			else:
				break
			row += 1
	def _update_suggestions(self, query):
		new_suggestions = self.get_suggestions(query)
		diff = diff_lists(self._curr_suggestions, new_suggestions)
		class AsList:
			def __init__(self, target):
				self.target = target
			def __len__(self):
				return len(self.target._curr_suggestions)
			def __getitem__(self, i):
				return self.target._curr_suggestions[i]
			def __delitem__(self, i):
				del self.target._curr_suggestions[i]
				self.target._suggestions.takeItem(i)
			def insert(self, index, value):
				self.target._curr_suggestions.insert(index, value)
				self.target._add_suggestion(value, index)
		apply_list_diff(diff, AsList(self))
		self._shrink_suggestion_list_to_size()
	def _shrink_suggestion_list_to_size(self, num_visible=None, max_height=400):
		if num_visible is None:
			num_visible = self._suggestions.count()
		height = num_visible * self._suggestions.sizeHintForRow(0)
		if height > max_height:
			self._suggestions.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
		else:
			self._suggestions.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
		self._suggestions.setMaximumHeight(min(height, max_height))
	def _layout_vertically(self, parent, *widgets):
		layout = QVBoxLayout()
		layout.setContentsMargins(0, 0, 0, 0)
		layout.setSpacing(0)
		layout.setAlignment(Qt.AlignTop)
		for widget in widgets:
			layout.addWidget(widget)
		parent.setLayout(layout)
		return parent

class QuickSearchResult(QLabel):
	def __init__(self, result, parent):
		text, char_indices_to_highlight = result
		html_parts = list(text)
		for i in char_indices_to_highlight:
			html_parts[i] = '<font color="white">' + \
							html.escape(html_parts[i]) + '</font>'
		super().__init__(''.join(html_parts), parent)

def diff_lists(old, new):
	if not old and new:
		return [new]
	result = []
	for old_item in old:
		try:
			cut = new.index(old_item) + 1
		except ValueError as not_found:
			fragment = []
		else:
			fragment = new[:cut]
			new = new[cut:]
		result.append(fragment)
	if result:
		result[-1].extend(new)
	return result

def apply_list_diff(diff, list_):
	offset = 0
	for i, fragment in enumerate(diff):
		try:
			item = list_[i + offset]
		except IndexError:
			assert i + offset == len(list_)
			add_before = fragment
			add_after = []
		else:
			try:
				split_point = fragment.index(item)
			except ValueError:
				del list_[i + offset]
				offset -= 1
				add_before = []
				add_after = fragment
			else:
				add_before = fragment[:split_point]
				add_after = fragment[split_point + 1:]
		for item in add_before:
			list_.insert(i + offset, item)
			offset += 1
		if add_after:
			offset += 1
		for item in add_after:
			list_.insert(i + offset, item)
			offset += 1

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