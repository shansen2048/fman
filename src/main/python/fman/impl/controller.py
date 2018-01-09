from fbs_runtime.system import is_mac
from fman.impl.util.qt import KeypadModifier, Key_Down, Key_Up, Key_Left, \
	Key_Right, Key_Return, Key_Enter, Key_Shift, Key_Control, Key_Meta, \
	Key_Alt, Key_AltGr, Key_CapsLock, Key_NumLock, Key_ScrollLock, ShiftModifier
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence
from weakref import WeakValueDictionary

class Controller:
	"""
	The main purpose of this class is to shield the rest of the `plugin`
	implementation from having to know about Qt.
	"""
	def __init__(
			self, window, plugin_support, nonexistent_shortcut_handler, metrics
	):
		self._window = window
		self._plugin_support = plugin_support
		self._nonexistent_shortcut_handler = nonexistent_shortcut_handler
		self._metrics = metrics
		self._panes = WeakValueDictionary()
	def on_pane_added(self, pane_widget):
		pane_widget.set_controller(self)
		pane = self._window.add_pane(pane_widget)
		self._panes[pane_widget] = pane
		pane_widget.location_changed.connect(self.on_location_changed)
		self._plugin_support.on_pane_added(pane)
	def on_location_changed(self, pane_widget):
		self._panes[pane_widget]._broadcast('on_path_changed')
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
			self._nonexistent_shortcut_handler(key_event, pane)
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

class QtKeyEvent:
	def __init__(self, key, modifiers):
		self.key = key
		self.modifiers = modifiers
	def matches(self, keys):
		if is_mac():
			keys = self._replace(keys, {'Cmd': 'Ctrl', 'Ctrl': 'Meta'})
		modifiers = self.modifiers
		if is_mac() and self.key in (Key_Down, Key_Up, Key_Left, Key_Right):
			# According to the Qt documentation ([1]), the KeypadModifier flag
			# is set when an arrow key is pressed on OS X because the arrow keys
			# are part of the keypad. We don't want our users to have to specify
			# this modifier in their keyboard binding files. So we overwrite
			# this behaviour of Qt.
			# [1]: http://doc.qt.io/qt-5/qt.html#KeyboardModifier-enum
			modifiers &= ~KeypadModifier
		key, modifiers, keys = self._alias_return_and_enter(modifiers, keys)
		return QKeySequence(modifiers | key).matches(QKeySequence(keys))
	def __str__(self):
		result = ''
		if self.modifiers:
			result += QKeySequence(self.modifiers).toString()
		for key in [k for k in dir(Qt) if k.startswith('Key_')]:
			if self.key == getattr(Qt, key):
				result += key[len('Key_'):]
				break
		else:
			result += '0x%02x' % self.key
		return result
	def is_modifier_only(self):
		return self.key in (
			Key_Shift, Key_Control, Key_Meta, Key_Alt, Key_AltGr, Key_CapsLock,
			Key_NumLock, Key_ScrollLock
		)
	def is_letter_only(self):
		return not self.modifiers & ~ShiftModifier and \
			   Qt.Key_A <= self.key <= Qt.Key_Z
	def is_digit_only(self):
		return not self.modifiers and Qt.Key_0 <= self.key <= Qt.Key_9
	def _alias_return_and_enter(self, modifiers, keys):
		# Qt has Key_Enter and Key_Return. The former is the Enter key on the
		# numpad. The latter is next to the characters. We want the user to
		# specify "Enter" for both:
		if self.key == Key_Enter:
			key = Key_Return
			modifiers &= ~KeypadModifier
		else:
			key = self.key
		return key, modifiers, self._replace(keys, {'Enter': 'Return'})
	def _replace(self, keys, replacements):
		return '+'.join(replacements.get(k, k) for k in keys.split('+'))
	def __hash__(self):
		return hash((int(self.key), int(self.modifiers)))
	def __eq__(self, other):
		if not isinstance(other, QtKeyEvent):
			return False
		return self.key == other.key and self.modifiers == other.modifiers
	def __ne__(self, other):
		return not self == other