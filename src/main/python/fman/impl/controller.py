from fman.util.qt import KeypadModifier, Key_Down, Key_Up, Key_Left, Key_Right
from fman.util.system import is_mac
from PyQt5.QtGui import QKeySequence

class Controller:
	def __init__(self, plugin_support, tracker):
		self.plugin_support = plugin_support
		self.tracker = tracker
	def on_key_pressed(self, pane, event):
		key = event.key()
		modifiers = event.modifiers()
		if is_mac() and key in (Key_Down, Key_Up, Key_Left, Key_Right):
			# According to the Qt documentation ([1]), the KeypadModifier flag
			# is set when an arrow key is pressed on OS X because the arrow keys
			# are part of the keypad. We don't want our users to have to specify
			# this modifier in their keyboard binding files. So we overwrite
			# this behaviour of Qt.
			# [1]: http://doc.qt.io/qt-5/qt.html#KeyboardModifier-enum
			modifiers &= ~KeypadModifier
		key_sequence = QKeySequence(modifiers | key)
		key_bindings = self.plugin_support.get_key_bindings_for_pane(pane)
		for binding in key_bindings:
			keys = binding.keys[0]
			if is_mac():
				keys_mac = {'Cmd': 'Ctrl', 'Ctrl': 'Meta'}
				keys = '+'.join(keys_mac.get(k, k) for k in keys.split('+'))
			if key_sequence.matches(QKeySequence(keys)):
				command = binding.command
				command_name = command.__class__.__name__
				self.tracker.track('Ran command', {
					'Command': command_name
				})
				try:
					command(**binding.args)
				except NotImplementedError:
					continue
				else:
					return True
		event.ignore()
		return False
	def on_doubleclicked(self, pane, file_path):
		self.tracker.track('Doubleclicked file')
		self.plugin_support.on_doubleclicked(pane, file_path)
	def on_file_renamed(self, pane, file_path, new_name):
		self.plugin_support.on_name_edited(pane, file_path, new_name)