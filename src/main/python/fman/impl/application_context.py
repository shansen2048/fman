from fman import PLATFORM
from fman.impl import MainWindow
from fman.impl.metrics import Metrics
from fman.impl.controller import Controller
from fman.impl.excepthook import Excepthook
from fman.impl.plugin import PluginSupport, find_plugin_dirs, PluginErrorHandler
from fman.impl.session import SessionManager
from fman.impl.updater import MacUpdater
from fman.impl.view import Style
from fman.util import system
from os import getenv, rename
from os.path import dirname, join, pardir, normpath, exists, expanduser
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFontDatabase, QColor, QPalette
from PyQt5.QtWidgets import QApplication, QStyleFactory

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
		self._excepthook = None
		self._main_window = None
		self._controller = None
		self._palette = None
		self._main_window_palette = None
		self._plugin_dirs = None
		self._session_manager = None
		self._stylesheet = None
		self._style = None
		self._metrics = None
	def initialize(self):
		self.excepthook.install()
		self.metrics.initialize()
		self.excepthook.user_id = self.metrics.user_id
		self.metrics.super_properties.update({
			'$os': PLATFORM, '$app_version': self.constants['version']
		})
		self.metrics.track('Started fman')
		# Ensure QApplication is initialized before anything else Qt-related:
		_ = self.app
		self._load_fonts()
		self.plugin_support.initialize()
		self.session_manager.on_startup(self.main_window)
	def on_main_window_shown(self):
		if self.updater:
			self.updater.start()
	def _load_fonts(self):
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
			self._app.setPalette(self.palette)
		return self._app
	@property
	def constants(self):
		if self._constants is None:
			with open(self.get_resource('constants.json'), 'r') as f:
				self._constants = json.load(f)
			self._postprocess_constants()
		return self._constants
	def _postprocess_constants(self):
		filter_path = join(
			self.get_resource(), pardir, pardir, 'filters', 'filter-local.json'
		)
		with open(filter_path, 'r') as f:
			filter_ = json.load(f)
		for key, value in self._constants.items():
			if isinstance(value, str):
				for filter_key, filter_value in filter_.items():
					value = value.replace('${%s}' % filter_key, filter_value)
				self._constants[key] = value
	@property
	def excepthook(self):
		if self._excepthook is None:
			self._excepthook = Excepthook(
				self.constants['rollbar_token'], self.constants['environment'],
				self.constants['version']
			)
		return self._excepthook
	@property
	def main_window(self):
		if self._main_window is None:
			self._main_window = MainWindow()
			plugin_dirs = self.plugin_dirs
			error_handler = \
				PluginErrorHandler(plugin_dirs, self._main_window)
			plugin_support = PluginSupport(plugin_dirs, error_handler)
			self.app.aboutToQuit.connect(plugin_support.on_quit)
			controller = Controller(plugin_support, self.metrics)
			self._main_window.set_controller(controller)
			self._main_window.setPalette(self.main_window_palette)
			self._main_window.shown.connect(self.on_main_window_shown)
			self._main_window.shown.connect(error_handler.on_main_window_shown)
			self._main_window.pane_added.connect(plugin_support.on_pane_added)
			self._main_window.closeEvent = \
				lambda _: self.session_manager.on_close(self.main_window)
		return self._main_window
	@property
	def plugin_dirs(self):
		if self._plugin_dirs is None:
			shipped_plugins = self.get_resource('Plugins')
			installed_plugins = join(get_data_dir(), 'Plugins')
			self._plugin_dirs = \
				find_plugin_dirs(shipped_plugins, installed_plugins)
		return self._plugin_dirs
	@property
	def plugin_support(self):
		return self.controller.plugin_support
	@property
	def plugin_error_handler(self):
		return self.plugin_support.error_handler
	@property
	def controller(self):
		return self.main_window.controller
	@property
	def metrics(self):
		if self._metrics is None:
			json_path = join(get_data_dir(), 'Local', 'Metrics.json')
			# TODO: Remove this migration some time after November 2016
			old_json_names = ['Installation.json', 'Usage.json']
			for old_json_name in old_json_names:
				old_json_path = join(get_data_dir(), 'Local', old_json_name)
				if exists(old_json_path) and not exists(json_path):
					rename(old_json_path, json_path)
			self._metrics = Metrics(self.constants['mixpanel_token'], json_path)
		return self._metrics
	@property
	def palette(self):
		if self._palette is None:
			self._palette = QPalette()
			self._palette.setColor(QPalette.Window, QColor(43, 43, 43))
			self._palette.setColor(QPalette.WindowText, Qt.white)
			self._palette.setColor(QPalette.Base, QColor(19, 19, 19))
			self._palette.setColor(QPalette.AlternateBase, QColor(66, 64, 59))
			self._palette.setColor(QPalette.ToolTipBase, QColor(19, 19, 19))
			self._palette.setColor(QPalette.ToolTipText, Qt.white)
			self._palette.setColor(QPalette.Light, QColor(0x44, 0x44, 0x44))
			self._palette.setColor(QPalette.Midlight, QColor(0x33, 0x33, 0x33))
			self._palette.setColor(QPalette.Button, QColor(0x29, 0x29, 0x29))
			self._palette.setColor(QPalette.Mid, QColor(0x25, 0x25, 0x25))
			self._palette.setColor(QPalette.Dark, QColor(0x20, 0x20, 0x20))
			self._palette.setColor(QPalette.Shadow, QColor(0x1d, 0x1d, 0x1d))
			self._palette.setColor(QPalette.Text, Qt.white)
			self._palette.setColor(
				QPalette.ButtonText, QColor(0xb6, 0xb3, 0xab)
			)
			self._palette.setColor(QPalette.Link, Qt.white)
			self._palette.setColor(QPalette.LinkVisited, Qt.white)
		return self._palette
	@property
	def main_window_palette(self):
		if self._main_window_palette is None:
			self._main_window_palette = QPalette(self.palette)
			self._main_window_palette.setColor(
				QPalette.Window, QColor(0x44, 0x44, 0x44)
			)
		return self._main_window_palette
	@property
	def session_manager(self):
		if self._session_manager is None:
			json_path = join(get_data_dir(), 'Local', 'Session.json')
			self._session_manager = SessionManager(json_path)
		return self._session_manager
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
		os_dir = join(res_dir, PLATFORM.lower())
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
		return self._updater
	def get_resource(self, *rel_path):
		if system.is_mac():
			rel_path = (pardir, 'Resources') + rel_path
		return normpath(join(dirname(sys.executable), *rel_path))
	def _postprocess_constants(self):
		pass