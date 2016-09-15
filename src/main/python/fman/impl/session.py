from base64 import b64encode, b64decode
from os.path import expanduser, dirname

import json

from os import makedirs

class SessionManager:

	DEFAULT_COLUMN_WIDTHS = [200, 75]
	DEFAULT_WINDOW_SIZE = (800, 450)

	def __init__(self, json_path):
		self.json_path = json_path
		self._json_dict = None
	def on_startup(self, main_window):
		try:
			with open(self.json_path, 'r') as f:
				self._json_dict = json.load(f)
		except FileNotFoundError:
			self._json_dict = {}
		self._apply_settings_to_pane(main_window, 'left_pane')
		self._apply_settings_to_pane(main_window, 'right_pane')
		self._restore_window_geometry(main_window)
	def _apply_settings_to_pane(self, main_window, pane_name):
		pane = getattr(main_window, pane_name)
		settings = self._json_dict.get(pane_name, {})
		pane.set_path(settings.get('location', expanduser('~')))
		col_widths = settings.get('col_widths', self.DEFAULT_COLUMN_WIDTHS)
		for i, width in enumerate(col_widths):
			pane.file_view.setColumnWidth(i, width)
	def _restore_window_geometry(self, main_window):
		geometry_b64 = self._json_dict.get('window_geometry', None)
		if geometry_b64:
			main_window.restoreGeometry(_decode(geometry_b64))
		else:
			main_window.resize(*self.DEFAULT_WINDOW_SIZE)
		window_state_b64 = self._json_dict.get('window_state', None)
		if window_state_b64:
			main_window.restoreState(_decode(window_state_b64))
	def on_close(self, main_window):
		self._json_dict['window_geometry'] = _encode(main_window.saveGeometry())
		self._json_dict['window_state'] = _encode(main_window.saveState())
		left = main_window.left_pane
		right = main_window.right_pane
		self._json_dict['left_pane'] = self._read_settings_from_pane(left)
		self._json_dict['right_pane'] = self._read_settings_from_pane(right)
		makedirs(dirname(self.json_path), exist_ok=True)
		with open(self.json_path, 'w') as f:
			json.dump(self._json_dict, f)
	def _read_settings_from_pane(self, pane):
		return {
			'location': pane.get_path(),
			'col_widths': [pane.file_view.columnWidth(i) for i in (0, 1)]
		}

def _encode(bytes_):
	return b64encode(bytes_).decode('ascii')

def _decode(str_b64):
	return b64decode(str_b64)