from fman.impl import MainWindow
from fman.impl.controller import Controller
from fman.impl.os_ import OSX, Windows, Linux
from fman.impl.view import Style
from fman.util import system
from fman.util.qt import GuiThread
from fman.impl.settings import Settings, SettingsManager
from os.path import dirname, join, pardir, expanduser, normpath
from PyQt5.QtCore import QDir, QSettings
from PyQt5.QtGui import QFontDatabase
from PyQt5.QtWidgets import QApplication

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
		self._settings_manager = None
		self._settings = None
		self._qt_settings = None
		self._os = None
		self._gui_thread = None
		self._stylesheet = None
		self._style = None
	def load_fonts(self):
		if system.is_linux():
			db = QFontDatabase()
			db.addApplicationFont(self.get_resource('OpenSans-Semibold.ttf'))
	@property
	def app(self):
		if self._app is None:
			self._app = QApplication(self.argv)
			self._app.setOrganizationName('fman.io')
			self._app.setOrganizationDomain('fman.io')
			self._app.setApplicationName('fman')
			self._app.setApplicationDisplayName('fman')
			self._app.setStyleSheet(self.stylesheet)
			self._app.setStyle(self.style)
			QDir.addSearchPath('image', self.get_resource('images'))
		return self._app
	@property
	def main_window(self):
		return self._main_window_and_controller[0]
	@property
	def controller(self):
		return self._main_window_and_controller[1]
	@property
	def _main_window_and_controller(self):
		assert (self._main_window is None) == (self._controller is None)
		if self._main_window is None:
			self._main_window = MainWindow()
			self._main_window.closeEvent = \
				lambda _: self.settings_manager.on_close(self.main_window)
			self._controller = Controller(
				self._main_window, self.os, self.settings, self.app,
				self.gui_thread
			)
			self._main_window.set_controller(self._controller)
		return self._main_window, self._controller
	@property
	def settings_manager(self):
		if self._settings_manager is None:
			self._settings_manager = \
				SettingsManager(self.settings, self.qt_settings)
		return self._settings_manager
	@property
	def settings(self):
		if self._settings is None:
			default_settings = self.get_resource('default_settings.json')
			custom_settings = expanduser(join('~', '.fman', 'settings.json'))
			self._settings = Settings(default_settings, custom_settings)
		return self._settings
	@property
	def qt_settings(self):
		if self._qt_settings is None:
			self._qt_settings = QSettings(
				expanduser(join('~', '.fman', 'qt_settings.ini')),
				QSettings.IniFormat
			)
		return self._qt_settings
	@property
	def os(self):
		if self._os is None:
			if system.is_osx():
				self._os = OSX()
			elif system.is_windows():
				self._os = Windows()
			elif system.is_linux():
				self._os = Linux()
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
			os_styles = None
			if system.is_windows():
				os_styles = 'windows.qss'
			elif system.is_linux():
				os_styles = 'linux.qss'
			if os_styles:
				with open(self.get_resource('styles', os_styles), 'r') as f:
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