from base64 import b64encode, b64decode
from os.path import expanduser, dirname

import json

from os import makedirs

class SessionManager:

	DEFAULT_NUM_PANES = 2
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
		default_panes = [{}] * self.DEFAULT_NUM_PANES
		for pane_info in self._json_dict.get('panes', default_panes):
			pane = main_window.add_pane()
			pane.set_path(pane_info.get('location', expanduser('~')))
			col_widths = pane_info.get('col_widths', self.DEFAULT_COLUMN_WIDTHS)
			for i, width in enumerate(col_widths):
				pane.file_view.setColumnWidth(i, width)
		self._restore_window_geometry(main_window)
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
		self._json_dict['panes'] = \
			list(map(self._read_settings_from_pane, main_window.get_panes()))
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