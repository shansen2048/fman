from os import makedirs
from os.path import exists, expanduser, dirname

import json

class Settings:
	def __init__(self, default_path, custom_path):
		self.default_path = default_path
		self.custom_path = custom_path
		with open(default_path, 'r') as default_settings:
			self._settings = json.load(default_settings)
		if exists(custom_path):
			with open(custom_path, 'r') as custom_settings:
				self._settings.update(json.load(custom_settings))
	def __getitem__(self, item):
		return self._settings[item]
	def apply(self, main_window, left_pane, right_pane):
		main_window.resize(self['window_width'], self['window_height'])
		self._apply_to_pane(self['left'], left_pane)
		self._apply_to_pane(self['right'], right_pane)
	def save(self, main_window, left_pane, right_pane):
		settings = {
			'window_width': main_window.width(),
			'window_height': main_window.height(),
			'left': self._read_from_pane(left_pane),
			'right': self._read_from_pane(right_pane)
		}
		makedirs(dirname(self.custom_path), exist_ok=True)
		with open(self.custom_path, 'w') as settings_file:
			json.dump(settings, settings_file)
	def _apply_to_pane(self, settings, pane):
		pane.set_path(expanduser(settings['location']))
		for i, width in enumerate(settings['col_widths']):
			pane.file_view.setColumnWidth(i, width)
	def _read_from_pane(self, pane):
		return {
			'location': pane.get_path(),
			'col_widths': [pane.file_view.columnWidth(i) for i in (0, 1)]
		}