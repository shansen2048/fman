from fman import PLATFORM, DATA_DIRECTORY, Window
from fman.impl.css_qt_bridge import CSSQtBridge
from fman.impl.licensing import User
from fman.impl.metrics import Metrics, ServerBackend, AsynchronousMetrics, \
	LoggingBackend
from fman.impl.controller import Controller
from fman.impl.excepthook import Excepthook, RollbarExcepthook
from fman.impl.model import GnomeFileIconProvider
from fman.impl.nonexistent_shortcut_handler import NonexistentShortcutHandler
from fman.impl.plugins import PluginSupport, SETTINGS_PLUGIN_NAME, \
	CommandCallback
from fman.impl.plugins.builtin import BuiltinPlugin
from fman.impl.plugins.discover import find_plugin_dirs
from fman.impl.plugins.error import PluginErrorHandler
from fman.impl.plugins.jsonio import JsonIO
from fman.impl.plugins.plugin import ExternalPlugin
from fman.impl.session import SessionManager
from fman.impl.signal_ import SignalWakeupHandler
from fman.impl.tutorial import Tutorial
from fman.impl.updater import MacUpdater
from fman.impl.view import Style
from fman.impl.widgets import MainWindow, SplashScreen, Application
from fman.util import system
from fman.util.settings import Settings
from glob import glob
from os.path import dirname, join, pardir, normpath, exists
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFontDatabase, QColor, QPalette, QIcon
from PyQt5.QtWidgets import QStyleFactory
from signal import signal, SIGINT

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
		self._command_callback = None
		self._config_file_locator = None
		self._constants = None
		self._css = None
		self._css_qt_bridge = None
		self._excepthook = None
		self._icon_provider = None
		self._main_window = None
		self._controller = None
		self._nonexistent_shortcut_handler = None
		self._palette = None
		self._user = None
		self._is_licensed = None
		self._main_window_palette = None
		self._plugins = None
		self._builtin_plugin = None
		self._plugin_support = None
		self._plugin_error_handler = None
		self._plugin_dirs = None
		self._json_io = None
		self._splash_screen = None
		self._tutorial = None
		self._signal_wakeup_handler = None
		self._session_manager = None
		self._stylesheet = None
		self._style = None
		self._metrics = None
		self._metrics_logging_enabled = None
		self._metrics_backend = None
		self._window = None
	def setup_signals(self):
		# We don't build fman as a console app on Windows, so no point in
		# installing the SIGINT handler:
		if not system.is_windows():
			_ = self.signal_wakeup_handler
			signal(SIGINT, lambda *_: self.app.exit(130))
	def run(self):
		fman.FMAN_VERSION = self.fman_version
		self.excepthook.install()
		self.metrics.initialize()
		self.metrics.track('StartedFman')
		self._load_fonts()
		# Ensure main_window is instantiated before plugin_support, or else
		# plugin_support gets instantiated twice:
		_ = self.main_window
		self.plugin_support.initialize()
		self.session_manager.show_main_window(self.main_window)
		return self.app.exec_()
	@property
	def fman_version(self):
		return self.constants['version']
	def on_main_window_shown(self):
		if self.updater:
			self.updater.start()
		if self.is_licensed:
			if not self.session_manager.was_licensed_on_last_run:
				self.metrics.track('InstalledLicenseKey')
				self.metrics.update_user(
					is_licensed=True, email=self.user.email
				)
		else:
			if self.session_manager.is_first_run:
				self.tutorial.start()
			else:
				self.splash_screen.exec()
	def on_main_window_close(self):
		self.session_manager.on_close(self.main_window)
	def on_quit(self):
		self.json_io.on_quit()
		if self.metrics_logging_enabled:
			log_dir = dirname(self._get_metrics_json_path())
			log_file_path = join(log_dir, 'Metrics.log')
			self.metrics_backend.flush(log_file_path)
	def _load_fonts(self):
		fonts_to_load = []
		for plugin_dir in self.plugin_dirs:
			fonts_to_load.extend(glob(join(plugin_dir, '*.ttf')))
		for font in fonts_to_load:
			QFontDatabase.addApplicationFont(font)
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
			self.app.aboutToQuit.connect(self.on_quit)
		return self._app
	@property
	def app_icon(self):
		if self._app_icon is None and not system.is_mac():
			self._app_icon = QIcon(self._get_resource('fman.ico'))
		return self._app_icon
	@property
	def command_callback(self):
		if self._command_callback is None:
			self._command_callback = CommandCallback(self.metrics)
		return self._command_callback
	@property
	def constants(self):
		if self._constants is None:
			with open(self._get_resource('constants.json'), 'r') as f:
				self._constants = json.load(f)
			self._postprocess_constants()
		return self._constants
	def _postprocess_constants(self):
		filter_path = join(
			self._get_resource(), pardir, pardir, 'filters', 'filter-local.json'
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
			self._excepthook = \
				Excepthook(self.plugin_dirs, self.plugin_error_handler)
		return self._excepthook
	@property
	def icon_provider(self):
		if self._icon_provider is None:
			try:
				self._icon_provider = GnomeFileIconProvider()
			except ImportError:
				pass
		return self._icon_provider
	@property
	def main_window(self):
		if self._main_window is None:
			self._main_window = \
				MainWindow(self.app, self.css, self.icon_provider)
			self._main_window.setWindowTitle(self._get_main_window_title())
			self._main_window.setPalette(self.main_window_palette)
			self._main_window.shown.connect(self.on_main_window_shown)
			self._main_window.shown.connect(
				lambda: self.plugin_error_handler.on_main_window_shown(
					self.main_window
				)
			)
			self._main_window.pane_added.connect(self.controller.on_pane_added)
			self._main_window.closed.connect(self.on_main_window_close)
			self.app.set_main_window(self._main_window)
		return self._main_window
	def _get_main_window_title(self):
		if self.is_licensed:
			return 'fman'
		return 'fman – NOT REGISTERED'
	@property
	def plugins(self):
		if self._plugins is None:
			def external_plugin(dir_):
				return self._instantiate_plugin(ExternalPlugin, dir_)
			self._plugins = [self.builtin_plugin] + \
							list(map(external_plugin, self._plugin_dirs))
		return self._plugins
	@property
	def builtin_plugin(self):
		if self._builtin_plugin is None:
			self._builtin_plugin = \
				self._instantiate_plugin(BuiltinPlugin, self.tutorial)
		return self._builtin_plugin
	def _instantiate_plugin(self, cls, *args):
		return cls(self.plugin_error_handler, self.command_callback, *args)
	@property
	def plugin_dirs(self):
		if self._plugin_dirs is None:
			self._plugin_dirs = find_plugin_dirs(
				self._get_resource('Plugins'),
				join(DATA_DIRECTORY, 'Plugins', 'Third-party'),
				join(DATA_DIRECTORY, 'Plugins', 'User')
			)
		return self._plugin_dirs
	@property
	def json_io(self):
		if self._json_io is None:
			self._json_io = JsonIO(self._get_config_dirs(), PLATFORM)
		return self._json_io
	def _get_config_dirs(self):
		result = list(self.plugin_dirs)
		settings_plugin = \
			join(DATA_DIRECTORY, 'Plugins', 'User', SETTINGS_PLUGIN_NAME)
		if settings_plugin not in result:
			# We want the Settings plugin to appear in the list of config files
			# even if it does not exist, because it serves as the default
			# destination for save_json(...):
			result.append(settings_plugin)
		return result
	@property
	def splash_screen(self):
		if self._splash_screen is None:
			self._splash_screen = SplashScreen(self.main_window, self.app)
		return self._splash_screen
	@property
	def tutorial(self):
		if self._tutorial is None:
			self._tutorial = Tutorial(
				self.main_window, self.app, self.command_callback, self.metrics
			)
		return self._tutorial
	@property
	def plugin_support(self):
		if self._plugin_support is None:
			self._plugin_support = PluginSupport(
				self.plugins, self.json_io, self.plugin_error_handler
			)
		return self._plugin_support
	@property
	def plugin_error_handler(self):
		if self._plugin_error_handler is None:
			self._plugin_error_handler = PluginErrorHandler(self.app)
		return self._plugin_error_handler
	@property
	def controller(self):
		if self._controller is None:
			self._controller = Controller(
				self.window, self.plugin_support,
				self.nonexistent_shortcut_handler, self.metrics
			)
		return self._controller
	@property
	def nonexistent_shortcut_handler(self):
		if self._nonexistent_shortcut_handler is None:
			settings = Settings(self._get_local_data_file('Dialogs.json'))
			self._nonexistent_shortcut_handler = NonexistentShortcutHandler(
				self.main_window, settings, self.metrics
			)
		return self._nonexistent_shortcut_handler
	@property
	def metrics(self):
		if self._metrics is None:
			json_path = self._get_metrics_json_path()
			metrics = Metrics(
				json_path, self.metrics_backend, PLATFORM, self.fman_version
			)
			self._metrics = AsynchronousMetrics(metrics)
		return self._metrics
	def _get_metrics_json_path(self):
		return self._get_local_data_file('Metrics.json')
	@property
	def metrics_logging_enabled(self):
		if self._metrics_logging_enabled is None:
			self._metrics_logging_enabled = self._read_metrics_logging_enabled()
		return self._metrics_logging_enabled
	def _read_metrics_logging_enabled(self):
		json_path = self._get_metrics_json_path()
		try:
			with open(json_path, 'r') as f:
				data = json.load(f)
		except (FileNotFoundError, ValueError):
			return False
		else:
			try:
				return data.get('logging_enabled', False)
			except AttributeError:
				return False
	@property
	def metrics_backend(self):
		if self._metrics_backend is None:
			metrics_url = self.constants['server_url'] + '/metrics'
			backend = \
				ServerBackend(metrics_url + '/users', metrics_url + '/events')
			if self.metrics_logging_enabled:
				backend = LoggingBackend(backend)
			self._metrics_backend = backend
		return self._metrics_backend
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
			json_path = self._get_local_data_file('User.json')
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
	def is_licensed(self):
		if self._is_licensed is None:
			self._is_licensed = self.user.is_licensed(self.fman_version)
		return self._is_licensed
	@property
	def main_window_palette(self):
		if self._main_window_palette is None:
			self._main_window_palette = QPalette(self.palette)
			self._main_window_palette.setColor(
				QPalette.Window, QColor(0x44, 0x44, 0x44)
			)
		return self._main_window_palette
	@property
	def signal_wakeup_handler(self):
		if self._signal_wakeup_handler is None:
			self._signal_wakeup_handler = SignalWakeupHandler(self.app)
		return self._signal_wakeup_handler
	@property
	def session_manager(self):
		if self._session_manager is None:
			settings = Settings(self._get_local_data_file('Session.json'))
			self._session_manager = \
				SessionManager(settings, self.fman_version, self.is_licensed)
		return self._session_manager
	@property
	def stylesheet(self):
		if self._stylesheet is None:
			with open(self._get_resource('styles.qss'), 'r') as f:
				self._stylesheet = f.read()
			os_styles = self._get_resource('os_styles.qss')
			if exists(os_styles):
				with open(os_styles, 'r') as f:
					self._stylesheet += '\n' + f.read()
			self._stylesheet += '\n' + self.css_qt_bridge.get_qss()
		return self._stylesheet
	@property
	def css(self):
		if self._css is None:
			self._css = self.css_qt_bridge.parse_css()
		return self._css
	@property
	def css_qt_bridge(self):
		if self._css_qt_bridge is None:
			css_paths = self.json_io.locate('Theme.css')
			self._css_qt_bridge = CSSQtBridge(css_paths)
		return self._css_qt_bridge
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
	def _get_resource(self, *rel_path):
		res_dir = join(dirname(__file__), pardir, pardir, pardir, 'resources')
		os_dir = join(res_dir, PLATFORM.lower())
		os_path = normpath(join(os_dir, *rel_path))
		if exists(os_path):
			return os_path
		base_dir = join(res_dir, 'base')
		return normpath(join(base_dir, *rel_path))
	def _get_local_data_file(self, file_name):
		return join(DATA_DIRECTORY, 'Local', file_name)

class FrozenApplicationContext(ApplicationContext):
	def __init__(self):
		super().__init__()
		self._updater = None
	@property
	def updater(self):
		if self._updater is None:
			if self._should_auto_update():
				self._updater = MacUpdater(self.app)
		return self._updater
	@property
	def excepthook(self):
		if self._excepthook is None:
			self._excepthook = RollbarExcepthook(
				self.constants['rollbar_token'], self.constants['environment'],
				self.fman_version, self.plugin_dirs, self.plugin_error_handler
			)
		return self._excepthook
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
	def _get_resource(self, *rel_path):
		if system.is_mac():
			rel_path = (pardir, 'Resources') + rel_path
		return normpath(join(dirname(sys.executable), *rel_path))
	def _postprocess_constants(self):
		pass