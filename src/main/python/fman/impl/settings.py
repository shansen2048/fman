from base64 import b64encode, b64decode
from os import makedirs
from os.path import exists, expanduser, dirname

import json

class SessionManager:

	DEFAULT_COLUMN_WIDTHS = [200, 75]
	DEFAULT_WINDOW_SIZE = (800, 450)

	def __init__(self, settings):
		self.settings = settings
	def on_startup(self, main_window):
		self._apply_settings_to_pane(main_window, 'left_pane')
		self._apply_settings_to_pane(main_window, 'right_pane')
		self._restore_window_geometry(main_window)
	def _apply_settings_to_pane(self, main_window, pane_name):
		pane = getattr(main_window, pane_name)
		settings = self.settings.get(pane_name, {})
		pane.set_path(expanduser(settings.get('location', '~')))
		col_widths = settings.get('col_widths', self.DEFAULT_COLUMN_WIDTHS)
		for i, width in enumerate(col_widths):
			pane.file_view.setColumnWidth(i, width)
	def _restore_window_geometry(self, main_window):
		geometry_b64 = self.settings.get('window_geometry', None)
		if geometry_b64:
			main_window.restoreGeometry(_decode(geometry_b64))
		else:
			main_window.resize(*self.DEFAULT_WINDOW_SIZE)
		window_state_b64 = self.settings.get('window_state', None)
		if window_state_b64:
			main_window.restoreState(_decode(window_state_b64))
	def on_close(self, main_window):
		self.settings['window_geometry'] = _encode(main_window.saveGeometry())
		self.settings['window_state'] = _encode(main_window.saveState())
		left_pane = main_window.left_pane
		right_pane = main_window.right_pane
		self.settings['left_pane'] = self._read_settings_from_pane(left_pane)
		self.settings['right_pane'] = self._read_settings_from_pane(right_pane)
	def _read_settings_from_pane(self, pane):
		return {
			'location': pane.get_path(),
			'col_widths': [pane.file_view.columnWidth(i) for i in (0, 1)]
		}

def _encode(bytes_):
	return b64encode(bytes_).decode('ascii')

def _decode(str_b64):
	return b64decode(str_b64)

class Settings:
	def __init__(self, json_paths):
		self._json_paths = json_paths
		self._dicts = []
		for json_path in json_paths:
			items = {}
			if exists(json_path):
				with open(json_path, 'r') as f:
					items = json.load(f)
			self._dicts.append(items)
	def __getitem__(self, item):
		for items in self._dicts:
			try:
				return items[item]
			except KeyError:
				pass
		raise KeyError(item)
	def __contains__(self, item):
		try:
			self[item]
		except KeyError:
			return False
		return True
	def __setitem__(self, key, value):
		try:
			if self[key] == value:
				return
		except KeyError:
			pass
		self._dicts[0][key] = value
		self._write_to_disk()
	def get(self, key, default):
		try:
			return self[key]
		except KeyError:
			return default
	def _write_to_disk(self):
		json_path = self._json_paths[0]
		makedirs(dirname(json_path), exist_ok=True)
		with open(json_path, 'w') as f:
			json.dump(self._dicts[0], f)