from fman.impl import DirectoryPaneController, DirectoryPane
from os.path import dirname, join, pardir, exists, expanduser
from PyQt5.QtWidgets import QApplication, QSplitter

import json

class ApplicationContext:
	def __init__(self, argv):
		self.argv = argv
		self._qapp = None
		self._main_window = None
		self._controller = None
		self._settings = None
	@property
	def qapp(self):
		if self._qapp is None:
			self._qapp = QApplication(self.argv)
			with open(self.get_resource('style.qss'), 'r') as style_file:
				stylesheet = style_file.read()
			self._qapp.setStyleSheet(stylesheet)
		return self._qapp
	@property
	def main_window(self):
		if self._main_window is None:
			self._main_window = QSplitter()
			self._main_window.addWidget(self.controller.left_pane)
			self._main_window.addWidget(self.controller.right_pane)
			self._main_window.setWindowTitle("fman")
			window_width = self.settings['window_width']
			window_height = self.settings['window_height']
			self._main_window.resize(window_width, window_height)
		return self._main_window
	@property
	def controller(self):
		if self._controller is None:
			self._controller = DirectoryPaneController()
			self._controller.left_pane = self._create_pane('left')
			self._controller.right_pane = self._create_pane('right')
		return self._controller
	def _create_pane(self, side):
		result = DirectoryPane(self._controller)
		settings = self.settings[side]
		location = expanduser(settings['location'])
		result.set_path(location)
		for i, width in enumerate(settings['col_widths']):
			result.file_view.setColumnWidth(i, width)
		return result
	@property
	def settings(self):
		if self._settings is None:
			default_settings_path = self.get_resource('default_settings.json')
			with open(default_settings_path, 'r') as default_settings_file:
				self._settings = json.load(default_settings_file)
			custom_settings_path = \
				expanduser(join('~', '.fman', 'settings.json'))
			if exists(custom_settings_path):
				with open(custom_settings_path, 'r') as custom_settings_file:
					self._settings.update(json.load(custom_settings_file))
		return self._settings
	def get_resource(self, *rel_path):
		resources_dir = \
			join(dirname(__file__), pardir, pardir, pardir, 'resources')
		return join(resources_dir, *rel_path)