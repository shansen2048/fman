from fman.impl.util.qt.key_event import QtKeyEvent
from PyQt5.QtGui import QContextMenuEvent
from weakref import WeakValueDictionary

class Controller:
	"""
	The main purpose of this class is to shield the rest of the `plugin`
	implementation from having to know about Qt.
	"""
	def __init__(self, plugin_support, nonexistent_shortcut_handler, metrics):
		self._plugin_support = plugin_support
		self._nonexistent_shortcut_handler = nonexistent_shortcut_handler
		self._metrics = metrics
		self._panes = WeakValueDictionary()
	def register_pane(self, pane_widget, pane):
		self._panes[pane_widget] = pane
		pane_widget.location_changed.connect(self.on_location_changed)
		pane_widget.location_bar_clicked.connect(self.on_location_bar_clicked)
		self._plugin_support.register_pane(pane)
	def on_location_changed(self, pane_widget):
		self._panes[pane_widget]._broadcast('on_path_changed')
	def on_location_bar_clicked(self, pane_widget):
		self._metrics.track('ClickedLocationBar')
		self._panes[pane_widget]._broadcast('on_location_bar_clicked')
	def on_key_pressed(self, pane_widget, event):
		pane = self._panes[pane_widget]
		key_event = QtKeyEvent(event.key(), event.modifiers())
		for key_binding in self._plugin_support.get_sanitized_key_bindings():
			keys = key_binding['keys']
			if key_event.matches(keys[0]):
				cmd_name = key_binding['command']
				args = key_binding.get('args', {})
				if cmd_name in pane.get_commands():
					pane.run_command(cmd_name, args)
				else:
					self._plugin_support.run_application_command(cmd_name, args)
				return True
		if not key_event.is_modifier_only() and \
			not key_event.is_letter_only() and \
			not key_event.is_digit_only():
			if self._nonexistent_shortcut_handler(key_event, pane):
				return True
		event.ignore()
		return False
	def on_doubleclicked(self, pane_widget, file_path):
		self._metrics.track('DoubleclickedFile')
		self._panes[pane_widget]._broadcast('on_doubleclicked', file_path)
	def on_file_renamed(self, pane_widget, *args):
		self._metrics.track('RenamedFile')
		self._panes[pane_widget]._broadcast('on_name_edited', *args)
	def on_files_dropped(self, pane_widget, *args):
		self._metrics.track('DroppedFile')
		self._panes[pane_widget]._broadcast('on_files_dropped', *args)
	def on_context_menu(self, pane_widget, event, file_under_mouse):
		if event.reason() == QContextMenuEvent.Mouse:
			via = 'Mouse'
		elif event.reason() == QContextMenuEvent.Keyboard:
			via = 'Keyboard'
		else:
			assert event.reason() == QContextMenuEvent.Other, event.reason()
			via = 'Other'
		self._metrics.track('OpenedContextMenu', {'via': via})
		return self._plugin_support.get_context_menu(
			self._panes[pane_widget], file_under_mouse
		)