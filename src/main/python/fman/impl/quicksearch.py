from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QLabel, QLayout, QListWidget, \
	QListWidgetItem, QFrame, QGridLayout, QVBoxLayout, QLineEdit

import html

from fman import is_mac
from fman.util.qt import Key_Tab, Key_Down, Key_Up, Key_PageDown, Key_Home, \
	Key_End, Key_PageUp

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
		value = self._curr_items[index.row()].value if index.isValid() else None
		self._result = self._query.text(), value
		self.accept()
	def _on_key_pressed(self, event):
		if event.key() == Key_Tab:
			index = self._items.currentIndex()
			if index.isValid():
				item = self._curr_items[index.row()]
				completion = self.get_tab_completion(item.value)
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
		if not isinstance(self._curr_items, list):
			self._curr_items = list(self._curr_items)
		for item in self._curr_items:
			self._add_item(item)
		self._shrink_item_list_to_size()
	def _add_item(self, item):
		widget_item = QListWidgetItem("")
		widget = QuicksearchItem(
			self._items, item.title, item.highlight, item.hint, item.description
		)
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
	def __init__(self, parent, title, highlight=None, hint='', description=''):
		super().__init__(parent)
		if highlight is None:
			highlight = []
		layout = QGridLayout()
		layout.setContentsMargins(0, 0, 0, 0)
		layout.setSpacing(0)

		title_text = QLabel(self._get_title_html(title, highlight), self)
		title_text.setTextFormat(Qt.RichText)
		title_text.setObjectName('title')
		layout.addWidget(title_text, 0, 0)

		if hint:
			hint_widget = QLabel(hint, self)
			hint_widget.setObjectName('hint')
			layout.addWidget(hint_widget, 0, 1)
			layout.setColumnStretch(0, 2)

		if description:
			descr_widget = QLabel(description, self)
			layout.addWidget(descr_widget, 1, 0)

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