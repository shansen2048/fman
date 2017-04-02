from fman import PLATFORM, DATA_DIRECTORY, Window
from fman.impl.css_to_qss import css_rules_to_qss
from fman.impl.licensing import User
from fman.impl.metrics import Metrics
from fman.impl.controller import Controller
from fman.impl.excepthook import Excepthook
from fman.impl.model import GnomeFileIconProvider
from fman.impl.plugins import PluginSupport, USER_PLUGIN_NAME
from fman.impl.plugins.config import ConfigFileLocator
from fman.impl.plugins.config.css import load_css_rules
from fman.impl.plugins.config.json_ import JsonIO
from fman.impl.plugins.discover import find_plugin_dirs
from fman.impl.plugins.error import PluginErrorHandler
from fman.impl.session import SessionManager
from fman.impl.updater import MacUpdater
from fman.impl.view import Style
from fman.impl.widgets import MainWindow, SplashScreen, Application
from fman.util import system
from glob import glob
from os.path import dirname, join, pardir, normpath, exists
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFontDatabase, QColor, QPalette, QIcon
from PyQt5.QtWidgets import QStyleFactory

import fman
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
		self._app_icon = None
		self._config_file_locator = None
		self._constants = None
		self._excepthook = None
		self._icon_provider = None
		self._main_window = None
		self._controller = None
		self._palette = None
		self._user = None
		self._main_window_palette = None
		self._plugin_dirs = None
		self._json_io = None
		self._splash_screen = None
		self._session_manager = None
		self._stylesheet = None
		self._style = None
		self._metrics = None
		self._window = None
	def initialize(self):
		self.excepthook.install()
		self.metrics.initialize()
		self.excepthook.user_id = self.metrics.user_id
		self.metrics.super_properties.update({
			'$os': PLATFORM, '$app_version': self.fman_version
		})
		self.metrics.track('Started fman')
		# Ensure QApplication is initialized before anything else Qt-related:
		_ = self.app
		self._load_fonts()
		fman.FMAN_VERSION = self.fman_version
		self.plugin_support.initialize()
		self.session_manager.on_startup(self.main_window)
	@property
	def fman_version(self):
		return self.constants['version']
	def on_main_window_shown(self):
		if self.updater:
			self.updater.start()
		if not self.user.is_licensed(self.fman_version):
			self.splash_screen.exec()
	def _load_fonts(self):
		fonts_to_load = []
		for plugin_dir in self.plugin_dirs:
			fonts_to_load.extend(glob(join(plugin_dir, '*.ttf')))
		if fonts_to_load:
			db = QFontDatabase()
			for font in fonts_to_load:
				db.addApplicationFont(font)
	@property
	def app(self):
		if self._app is None:
			self._app = Application([sys.argv[0]])
			self._app.setOrganizationName('fman.io')
			self._app.setOrganizationDomain('fman.io')
			self._app.setApplicationName('fman')
			self._app.setStyleSheet(self.stylesheet)
			self._app.setStyle(self.style)
			self._app.setPalette(self.palette)
			if self.app_icon:
				self._app.setWindowIcon(self.app_icon)
		return self._app
	@property
	def app_icon(self):
		if self._app_icon is None and not system.is_mac():
			self._app_icon = QIcon(self.get_resource('fman.ico'))
		return self._app_icon
	@property
	def config_file_locator(self):
		if self._config_file_locator is None:
			self._config_file_locator = \
				ConfigFileLocator(self._get_config_dirs(), PLATFORM)
		return self._config_file_locator
	def _get_config_dirs(self):
		result = list(self.plugin_dirs)
		user_plugin = join(DATA_DIRECTORY, 'Plugins', USER_PLUGIN_NAME)
		if user_plugin not in result:
			# We want the User plugin to appear in the list of config files
			# even if it does not exist, because it serves as the default
			# destination for save_json(...):
			result.append(user_plugin)
		return result
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
				self.fman_version
			)
		return self._excepthook
	@property
	def icon_provider(self):
		if self._icon_provider is None and system.is_gnome_based():
			self._icon_provider = GnomeFileIconProvider()
		return self._icon_provider
	@property
	def main_window(self):
		if self._main_window is None:
			self._main_window = MainWindow(self.icon_provider)
			self._main_window.setWindowTitle(self._get_main_window_title())
			plugin_dirs = self.plugin_dirs
			error_handler = PluginErrorHandler(self.app, self._main_window)
			plugin_support = \
				PluginSupport(plugin_dirs, self.json_io, error_handler)
			controller = Controller(self.window, plugin_support, self.metrics)
			self._main_window.set_controller(controller)
			self._main_window.setPalette(self.main_window_palette)
			self._main_window.shown.connect(self.on_main_window_shown)
			self._main_window.shown.connect(error_handler.on_main_window_shown)
			self._main_window.pane_added.connect(controller.on_pane_added)
			self._main_window.closed.connect(
				lambda: self.session_manager.on_close(self.main_window)
			)
			self.app.set_main_window(self._main_window)
		return self._main_window
	def _get_main_window_title(self):
		if self.user.is_licensed(self.fman_version):
			return 'fman'
		return 'fman – NOT REGISTERED'
	@property
	def plugin_dirs(self):
		if self._plugin_dirs is None:
			shipped_plugins = self.get_resource('Plugins')
			installed_plugins = join(DATA_DIRECTORY, 'Plugins')
			self._plugin_dirs = \
				find_plugin_dirs(shipped_plugins, installed_plugins)
		return self._plugin_dirs
	@property
	def json_io(self):
		if self._json_io is None:
			self._json_io = JsonIO(self.config_file_locator)
			self.app.aboutToQuit.connect(self._json_io.on_quit)
		return self._json_io
	@property
	def splash_screen(self):
		if self._splash_screen is None:
			self._splash_screen = SplashScreen(self.main_window, self.app)
		return self._splash_screen
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
			json_path = join(DATA_DIRECTORY, 'Local', 'Metrics.json')
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
			self._palette.setColor(QPalette.Light, QColor(0x49, 0x48, 0x3E))
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
	def user(self):
		if self._user is None:
			json_path = join(DATA_DIRECTORY, 'Local', 'User.json')
			try:
				with open(json_path, 'r') as f:
					data = json.load(f)
			except (IOError, ValueError):
				data = {}
			email = data.get('email', '')
			key = data.get('key', '')
			self._user = User(email, key)
		return self._user
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
			json_path = join(DATA_DIRECTORY, 'Local', 'Session.json')
			self._session_manager = SessionManager(json_path, self.fman_version)
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
			css_rules = load_css_rules(*self.config_file_locator('Theme.css'))
			self._stylesheet += '\n' + css_rules_to_qss(css_rules)
		return self._stylesheet
	@property
	def style(self):
		if self._style is None:
			self._style = Style(QStyleFactory.create('Fusion'))
		return self._style
	@property
	def updater(self):
		return None
	@property
	def window(self):
		if self._window is None:
			self._window = Window()
		return self._window
	def get_resource(self, *rel_path):
		res_dir = join(dirname(__file__), pardir, pardir, pardir, 'resources')
		os_dir = join(res_dir, PLATFORM.lower())
		os_path = normpath(join(os_dir, *rel_path))
		if exists(os_path):
			return os_path
		base_dir = join(res_dir, 'base')
		return normpath(join(base_dir, *rel_path))

class FrozenApplicationContext(ApplicationContext):
	def __init__(self):
		super().__init__()
		self._updater = None
	@property
	def updater(self):
		if self._updater is None:
			if self._should_auto_update():
				appcast_url = self.constants['update_url'] + '/Appcast.xml'
				self._updater = MacUpdater(self.app, appcast_url)
		return self._updater
	def _should_auto_update(self):
		if not system.is_mac():
			# On Windows and Linux, auto-updates are handled by external
			# technologies. No need for fman itself to update:
			return False
		if not self.user.is_entitled_to_updates():
			return False
		try:
			with open(join(DATA_DIRECTORY, 'Local', 'Updates.json'), 'r') as f:
				data = json.load(f)
		except (FileNotFoundError, ValueError):
			return True
		else:
			return data.get('enabled', True)
	def get_resource(self, *rel_path):
		if system.is_mac():
			rel_path = (pardir, 'Resources') + rel_path
		return normpath(join(dirname(sys.executable), *rel_path))
	def _postprocess_constants(self):
		pass