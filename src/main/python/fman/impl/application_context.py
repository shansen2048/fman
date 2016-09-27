from fman import platform
from fman.impl import MainWindow
from fman.impl.controller import Controller
from fman.impl.plugin import PluginSupport
from fman.impl.session import SessionManager
from fman.impl.view import Style
from fman.updater import EskyUpdater, MacUpdater
from fman.util import system
from os import getenv
from os.path import dirname, join, pardir, normpath, exists, expanduser
from PyQt5.QtGui import QFontDatabase
from PyQt5.QtWidgets import QApplication, QStyleFactory
from shutil import rmtree

import json
import sys

def get_application_context():
	global _APPLICATION_CONTEXT
	if _APPLICATION_CONTEXT is None:
		is_frozen = getattr(sys, 'frozen', False)
		cls = FrozenApplicationContext if is_frozen else ApplicationContext
		_APPLICATION_CONTEXT = cls()
	return _APPLICATION_CONTEXT

_APPLICATION_CONTEXT = None

class ApplicationContext:
	def __init__(self):
		self._app = None
		self._constants = None
		self._main_window = None
		self._controller = None
		self._plugin_support = None
		self._session_manager = None
		self._stylesheet = None
		self._style = None
	def initialize(self):
		# Ensure QApplication is initialized before anything else:
		_ = self.app
		self.load_fonts()
		self.session_manager.on_startup(self.main_window)
		if self.updater:
			self.updater.start()
		self.plugin_support.initialize()
		# TODO: Remove this migration some time after mid October 2016:
		self._migrate_versions_lte_0_0_4()
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
			self._app = QApplication([sys.argv[0]])
			self._app.setOrganizationName('fman.io')
			self._app.setOrganizationDomain('fman.io')
			self._app.setApplicationName('fman')
			self._app.setApplicationDisplayName('fman')
			self._app.setStyleSheet(self.stylesheet)
			self._app.setStyle(self.style)
		return self._app
	@property
	def constants(self):
		if self._constants is None:
			with open(self.get_resource('constants.json'), 'r') as f:
				self._constants = json.load(f)
		return self._constants
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
			self._controller = Controller(self._main_window)
			self._main_window.set_controller(self._controller)
		return self._main_window, self._controller
	@property
	def plugin_support(self):
		if self._plugin_support is None:
			user_plugins = join(get_data_dir(), 'Plugins')
			shipped_plugins = self.get_resource('Plugins')
			self._plugin_support = \
				PluginSupport(user_plugins, shipped_plugins, self.controller)
		return self._plugin_support
	@property
	def session_manager(self):
		if self._session_manager is None:
			json_path = join(get_data_dir(), 'Local', 'Session.json')
			self._session_manager = SessionManager(json_path)
		return self._session_manager
	def _migrate_versions_lte_0_0_4(self):
		old_settings_dir = expanduser('~/.fman')
		try:
			with open(join(old_settings_dir, 'settings.json'), 'r') as f:
				old_settings = json.load(f)
		except FileNotFoundError:
			return
		try:
			editor = old_settings['editor']
			self.plugin_support.write_json(
				{'editor': editor}, 'Core Settings.json'
			)
		except KeyError:
			pass
		finally:
			rmtree(old_settings_dir)
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
		os_dir = join(res_dir, platform().lower())
		os_path = normpath(join(os_dir, *rel_path))
		if exists(os_path):
			return os_path
		base_dir = join(res_dir, 'base')
		return normpath(join(base_dir, *rel_path))

def get_data_dir():
	if system.is_mac():
		return expanduser('~/Library/Application Support/fman')
	if system.is_windows():
		return join(getenv('APPDATA'), 'fman')
	if system.is_linux():
		return expanduser('~/.config/fman')
	raise NotImplementedError('Your operating system is not supported.')

class FrozenApplicationContext(ApplicationContext):
	def __init__(self):
		super().__init__()
		self._updater = None
	@property
	def updater(self):
		if self._updater is None:
			update_url = self.constants['update_url']
			if system.is_mac():
				appcast_url = update_url + '/Appcast.xml'
				self._updater = MacUpdater(self.app, appcast_url)
			elif system.is_linux():
				self._updater = EskyUpdater(sys.executable, update_url)
		return self._updater
	def get_resource(self, *rel_path):
		if system.is_mac():
			rel_path = (pardir, 'Resources') + rel_path
		return normpath(join(dirname(sys.executable), *rel_path))