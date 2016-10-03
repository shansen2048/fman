from fman.util.qt import KeypadModifier, Key_Down, Key_Up, Key_Left, Key_Right
from fman.util.system import is_mac
from os import rename
from os.path import join, dirname
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QKeySequence, QDesktopServices

class Controller:
	def __init__(self, plugin_support, tracker):
		self.plugin_support = plugin_support
		self.tracker = tracker
	def key_pressed_in_file_view(self, view, event):
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
		pane = view.parentWidget()
		key_bindings = self.plugin_support.get_key_bindings_for_pane(pane)
		for binding in key_bindings:
			if key_sequence.matches(QKeySequence(binding.keys[0])):
				command = binding.command
				self.tracker.track('Ran command', {
					'Command': command.__class__.__name__
				})
				if command(**binding.args) is False:
					break
				return True
		event.ignore()
		return False
	def activated(self, model, file_view, index):
		file_path = model.filePath(index)
		if model.isDir(index):
			file_view.parentWidget().set_path(file_path)
		else:
			QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
	def file_renamed(self, pane, model, index, new_name):
		if not new_name:
			return
		src = model.filePath(index)
		dest = join(dirname(src), new_name)
		rename(src, dest)
		pane.file_view.place_cursor_at(dest)