from fman.impl import MainWindow
from fman.impl.controller import Controller
from fman.impl.os_ import OSX, Windows, Linux
from fman.impl.view import Style
from fman.updater import EskyUpdater, OSXUpdater
from fman.util import system
from fman.util.system import get_canonical_os_name
from fman.impl.settings import Settings, SessionManager
from os import makedirs
from os.path import dirname, join, pardir, normpath, exists, expanduser
from PyQt5.QtGui import QFontDatabase
from PyQt5.QtWidgets import QApplication, QStyleFactory
from shutil import rmtree

import json
import sys

def get_application_context(argv):
	if getattr(sys, 'frozen', False):
		return CompiledApplicationContext(argv)
	return ApplicationContext(argv)

class ApplicationContext:
	def __init__(self, argv):
		self.argv = argv
		self._app = None
		self._clipboard = None
		self._main_window = None
		self._controller = None
		self._session_manager = None
		self._settings = None
		self._session_settings = None
		self._os = None
		self._stylesheet = None
		self._style = None
	def load_fonts(self):
		if system.is_linux():
			db = QFontDatabase()
			db.addApplicationFont(self.get_resource('OpenSans-Semibold.ttf'))
		elif system.is_windows():
			db = QFontDatabase()
			db.addApplicationFont(self.get_resource('Roboto-Bold.ttf'))
	@property
	def app(self):
		if self._app is None:
			self._app = QApplication(self._get_qapplication_argv())
			self._app.setOrganizationName('fman.io')
			self._app.setOrganizationDomain('fman.io')
			self._app.setApplicationName('fman')
			self._app.setApplicationDisplayName('fman')
			self._app.setStyleSheet(self.stylesheet)
			self._app.setStyle(self.style)
		return self._app
	@property
	def clipboard(self):
		if self._clipboard is None:
			self._clipboard = self.app.clipboard()
		return self._clipboard
	def _get_qapplication_argv(self):
		return [self.argv[0]]
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
				lambda _: self.session_manager.on_close(self.main_window)
			self._controller = Controller(
				self._main_window, self.os, self.settings, self.clipboard
			)
			self._main_window.set_controller(self._controller)
		return self._main_window, self._controller
	@property
	def session_manager(self):
		if self._session_manager is None:
			self._session_manager = SessionManager(self.session_settings)
		return self._session_manager
	@property
	def settings(self):
		if self._settings is None:
			custom_settings_path = \
				join(self.os.get_data_dir(), 'Plugins', 'User', 'Settings.json')
			# TODO: Remove this migration some time after mid October 2016:
			self._migrate_versions_lte_0_0_4(custom_settings_path)
			default_settings = self.get_resource('Settings.json')
			self._settings = Settings([custom_settings_path, default_settings])
		return self._settings
	def _migrate_versions_lte_0_0_4(self, new_settings_path):
		old_settings_dir = expanduser('~/.fman')
		if not exists(old_settings_dir):
			return
		try:
			with open(join(old_settings_dir, 'settings.json'), 'r') as f:
				old_settings = json.load(f)
		except IOError:
			pass
		else:
			try:
				editor = old_settings['editor']
			except KeyError:
				pass
			else:
				if not exists(new_settings_path):
					makedirs(dirname(new_settings_path), exist_ok=True)
					with open(new_settings_path, 'w') as f:
						json.dump({'editor': editor}, f)
		rmtree(old_settings_dir)
	@property
	def session_settings(self):
		if self._session_settings is None:
			json_path = join(self.os.get_data_dir(), 'Cache', 'Session.json')
			return Settings([json_path])
		return self._session_settings
	@property
	def os(self):
		if self._os is None:
			if system.is_osx():
				self._os = OSX(self.clipboard)
			elif system.is_windows():
				self._os = Windows(self.clipboard)
			elif system.is_linux():
				self._os = Linux(self.clipboard)
			else:
				raise NotImplementedError('This OS is not yet supported.')
		return self._os
	@property
	def stylesheet(self):
		if self._stylesheet is None:
			with open(self.get_resource('styles.qss'), 'r') as f:
				self._stylesheet = f.read()
			os_styles = self.get_resource('os_styles.qss')
			if exists(os_styles):
				with open(os_styles, 'r') as f:
					self._stylesheet += '\n' + f.read()
		return self._stylesheet
	@property
	def style(self):
		if self._style is None:
			self._style = Style(QStyleFactory.create('Fusion'))
		return self._style
	@property
	def updater(self):
		return None
	def get_resource(self, *rel_path):
		res_dir = join(dirname(__file__), pardir, pardir, pardir, 'resources')
		os_dir = join(res_dir, get_canonical_os_name())
		os_path = normpath(join(os_dir, *rel_path))
		if exists(os_path):
			return os_path
		base_dir = join(res_dir, 'base')
		return normpath(join(base_dir, *rel_path))

class CompiledApplicationContext(ApplicationContext):
	def __init__(self, argv):
		super().__init__(argv)
		self._updater = None
	@property
	def updater(self):
		if self._updater is None:
			update_url = self.settings['update_url']
			if system.is_osx():
				appcast_url = update_url + '/Appcast.xml'
				self._updater = OSXUpdater(self.app, appcast_url)
			elif system.is_linux():
				self._updater = EskyUpdater(sys.executable, update_url)
		return self._updater
	def get_resource(self, *rel_path):
		if system.is_osx():
			rel_path = (pardir, 'Resources') + rel_path
		return normpath(join(dirname(sys.executable), *rel_path))