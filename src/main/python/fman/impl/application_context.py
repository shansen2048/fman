from fman.impl import DirectoryPaneController, DirectoryPane
from fman.impl.os_ import OSX, Windows
from fman.impl.view import Style
from fman.util import system
from fman.util.qt import GuiThread
from fman.impl.settings import Settings
from os.path import dirname, join, pardir, expanduser, normpath
from PyQt5.QtCore import QDir
from PyQt5.QtWidgets import QApplication, QSplitter

import sys

def get_application_context(argv):
	if getattr(sys, 'frozen', False):
		return CompiledApplicationContext(argv)
	return ApplicationContext(argv)

class ApplicationContext:
	def __init__(self, argv):
		self.argv = argv
		self._app = None
		self._main_window = None
		self._controller = None
		self._settings = None
		self._os = None
		self._gui_thread = None
		self._stylesheet = None
		self._style = None
	@property
	def app(self):
		if self._app is None:
			self._app = QApplication(self.argv)
			self._app.setApplicationDisplayName('fman')
			self._app.setStyleSheet(self.stylesheet)
			self._app.setStyle(self.style)
			QDir.addSearchPath('image', self.get_resource('images'))
		return self._app
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
			self._controller = DirectoryPaneController(
				self.os, self.settings, self.app, self.gui_thread
			)
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
			default_settings = self.get_resource('default_settings.json')
			custom_settings = expanduser(join('~', '.fman', 'settings.json'))
			self._settings = Settings(default_settings, custom_settings)
		return self._settings
	@property
	def os(self):
		if self._os is None:
			if system.is_osx():
				self._os = OSX()
			elif system.is_windows():
				self._os = Windows()
			else:
				raise NotImplementedError('This OS is not yet supported.')
		return self._os
	@property
	def gui_thread(self):
		if self._gui_thread is None:
			self._gui_thread = GuiThread()
		return self._gui_thread
	@property
	def stylesheet(self):
		if self._stylesheet is None:
			with open(self.get_resource('styles', 'base.qss'), 'r') as f:
				self._stylesheet = f.read()
			if system.is_windows():
				with open(self.get_resource('styles', 'windows.qss'), 'r') as f:
					self._stylesheet += '\n' + f.read()
		return self._stylesheet
	@property
	def style(self):
		if self._style is None:
			self._style = Style()
		return self._style
	def get_resource(self, *rel_path):
		res_dir = join(dirname(__file__), pardir, pardir, pardir, 'resources')
		return normpath(join(res_dir, *rel_path))

class CompiledApplicationContext(ApplicationContext):
	def get_resource(self, *rel_path):
		return normpath(join(dirname(sys.executable), *rel_path))