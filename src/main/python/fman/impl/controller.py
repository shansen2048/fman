from fman.impl.plugins.plugin import get_command_class_name
from fman.util.qt import KeypadModifier, Key_Down, Key_Up, Key_Left, Key_Right
from fman.util.system import is_mac
from PyQt5.QtGui import QKeySequence
from weakref import WeakValueDictionary

class Controller:
	"""
	The main purpose of this class is to shield the rest of the `plugin`
	implementation from having to know about Qt.
	"""
	def __init__(self, window, plugin_support, tracker):
		self.window = window
		self.plugin_support = plugin_support
		self.tracker = tracker
		self._panes = WeakValueDictionary()
	def on_pane_added(self, pane_widget):
		pane = self.window.add_pane(pane_widget)
		self._panes[pane_widget] = pane
		pane_widget.path_changed.connect(self.on_path_changed)
		self.plugin_support.on_pane_added(pane)
	def on_path_changed(self, pane_widget):
		self._panes[pane_widget]._broadcast('on_path_changed')
	def on_key_pressed(self, pane_widget, event):
		key_event = QtKeyEvent(event.key(), event.modifiers())
		for key_binding in self.plugin_support.get_sanitized_key_bindings():
			keys = key_binding['keys']
			if key_event.matches(keys[0]):
				cmd_name = key_binding['command']
				args = key_binding.get('args', {})
				pane = self._panes[pane_widget]
				if cmd_name in pane.get_commands():
					pane.run_command(cmd_name, args)
				else:
					self.plugin_support.run_application_command(cmd_name, args)
				self._track_command(cmd_name)
				return True
		event.ignore()
		return False
	def on_doubleclicked(self, pane_widget, file_path):
		self.tracker.track('Doubleclicked file')
		self._panes[pane_widget]._broadcast('on_doubleclicked', file_path)
	def on_file_renamed(self, pane_widget, *args):
		self.tracker.track('Renamed file')
		self._panes[pane_widget]._broadcast('on_name_edited', *args)
	def on_files_dropped(self, pane_widget, *args):
		self.tracker.track('Dropped file(s)')
		self._panes[pane_widget]._broadcast('on_files_dropped', *args)
	def _track_command(self, command_name):
		self.tracker.track('Ran command', {
			'Command': get_command_class_name(command_name)
		})

class QtKeyEvent:
	def __init__(self, key, modifiers):
		self.key = key
		self.modifiers = modifiers
	def matches(self, keys):
		def replace_keys(replacements):
			return '+'.join(replacements.get(k, k) for k in keys.split('+'))
		if is_mac():
			keys = replace_keys({'Cmd': 'Ctrl', 'Ctrl': 'Meta'})
		modifiers = self.modifiers
		if is_mac() and self.key in (Key_Down, Key_Up, Key_Left, Key_Right):
			# According to the Qt documentation ([1]), the KeypadModifier flag
			# is set when an arrow key is pressed on OS X because the arrow keys
			# are part of the keypad. We don't want our users to have to specify
			# this modifier in their keyboard binding files. So we overwrite
			# this behaviour of Qt.
			# [1]: http://doc.qt.io/qt-5/qt.html#KeyboardModifier-enum
			modifiers &= ~KeypadModifier
		this_event = QKeySequence(modifiers | self.key)
		if 'Enter' in keys.split('+'):
			# Qt has keys 'Return' as well as 'Enter'. We want to treat them as
			# the same and expect the user to write 'Enter' in Key Bindings.json
			keys_return = replace_keys({'Enter': 'Return'})
			if this_event.matches(QKeySequence(keys_return)):
				return True
		return this_event.matches(QKeySequence(keys))