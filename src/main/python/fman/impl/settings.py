from os import makedirs
from os.path import exists, expanduser, dirname

import json

class SessionManager:
	def __init__(self, settings, qt_settings):
		self.settings = settings
		self.qt_settings = qt_settings
	def on_startup(self, main_window):
		left_pane = main_window.left_pane
		right_pane = main_window.right_pane
		self._apply_settings_to_pane(self.settings['left'], left_pane)
		self._apply_settings_to_pane(self.settings['right'], right_pane)
		self._restore_window_geometry(main_window)
	def on_close(self, main_window):
		self._save_window_geometry(main_window)
		left_pane = main_window.left_pane
		right_pane = main_window.right_pane
		self.settings['left'] = self._read_settings_from_pane(left_pane)
		self.settings['right'] = self._read_settings_from_pane(right_pane)
		self.settings.write_to_disk()
	def _restore_window_geometry(self, main_window):
		geometry = self.qt_settings.value('geometry')
		if geometry:
			main_window.restoreGeometry(geometry)
		else:
			# Default size:
			main_window.resize(800, 450)
		window_state = self.qt_settings.value('window_state')
		if window_state:
			main_window.restoreState(window_state)
	def _apply_settings_to_pane(self, settings, pane):
		pane.set_path(expanduser(settings['location']))
		for i, width in enumerate(settings['col_widths']):
			pane.file_view.setColumnWidth(i, width)
	def _save_window_geometry(self, main_window):
		self.qt_settings.setValue('geometry', main_window.saveGeometry())
		self.qt_settings.setValue('window_state', main_window.saveState())
		self.qt_settings.sync()
	def _read_settings_from_pane(self, pane):
		return {
			'location': pane.get_path(),
			'col_widths': [pane.file_view.columnWidth(i) for i in (0, 1)]
		}

class Settings:
	def __init__(self, default_path, custom_path):
		self.custom_settings_path = custom_path
		with open(default_path, 'r') as default_settings:
			self._default_settings = json.load(default_settings)
		if exists(custom_path):
			with open(custom_path, 'r') as custom_settings:
				self._custom_settings = json.load(custom_settings)
		else:
			self._custom_settings = {}
	def __getitem__(self, item):
		try:
			return self._custom_settings[item]
		except KeyError:
			return self._default_settings[item]
	def __setitem__(self, key, value):
		if self[key] != value:
			self._custom_settings[key] = value
	def write_to_disk(self):
		if self._custom_settings:
			makedirs(dirname(self.custom_settings_path), exist_ok=True)
			with open(self.custom_settings_path, 'w') as settings_file:
				json.dump(self._custom_settings, settings_file)