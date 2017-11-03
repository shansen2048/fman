from fman import PLATFORM, DATA_DIRECTORY, Window
from fman.impl.font_database import FontDatabase
from fman.impl.plugins.key_bindings import KeyBindings
from fman.impl.theme import Theme
from fman.impl.licensing import User
from fman.impl.metrics import Metrics, ServerBackend, AsynchronousMetrics, \
	LoggingBackend
from fman.impl.controller import Controller
from fman.impl.excepthook import Excepthook, RollbarExcepthook
from fman.impl.model.icon_provider import GnomeFileIconProvider, \
	GnomeNotAvailable, IconProvider
from fman.impl.model.fs import DefaultFileSystem, ZipFileSystem
from fman.impl.nonexistent_shortcut_handler import NonexistentShortcutHandler
from fman.impl.plugins import PluginSupport, CommandCallback
from fman.impl.plugins.builtin import BuiltinPlugin
from fman.impl.plugins.discover import find_plugin_dirs
from fman.impl.plugins.error import PluginErrorHandler
from fman.impl.plugins.config import Config
from fman.impl.plugins.mother_fs import MotherFileSystem
from fman.impl.session import SessionManager
from fman.impl.signal_ import SignalWakeupHandler
from fman.impl.tutorial import Tutorial
from fman.impl.updater import MacUpdater
from fman.impl.view import Style
from fman.impl.widgets import MainWindow, SplashScreen, Application
from fman.util import system, cached_property, is_frozen
from fman.util.settings import Settings
from os import makedirs
from os.path import dirname, join, pardir, normpath, exists
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPalette, QIcon
from PyQt5.QtWidgets import QStyleFactory, QFileIconProvider
from signal import signal, SIGINT

import fman
import json
import logging
import sys

def get_application_context():
	global _APPLICATION_CONTEXT
	if _APPLICATION_CONTEXT is None:
		cls = FrozenApplicationContext if is_frozen() else ApplicationContext
		_APPLICATION_CONTEXT = cls()
	return _APPLICATION_CONTEXT

_APPLICATION_CONTEXT = None

class ApplicationContext:
	def __init__(self):
		self._main_window = None
	def setup_signals(self):
		# We don't build fman as a console app on Windows, so no point in
		# installing the SIGINT handler:
		if not system.is_windows():
			_ = self.signal_wakeup_handler
			signal(SIGINT, lambda *_: self.app.exit(130))
	def run(self):
		self.init_logging()
		fman.FMAN_VERSION = self.fman_version
		self.excepthook.install()
		self.metrics.initialize()
		self.metrics.track('StartedFman')
		# Ensure main_window is instantiated before plugin_support, or else
		# plugin_support gets instantiated twice:
		_ = self.main_window
		for plugin_dir in self.plugin_dirs:
			self.plugin_support.load_plugin(plugin_dir)
		self.session_manager.show_main_window(self.main_window)
		return self.app.exec_()
	def init_logging(self):
		logging.basicConfig()
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
		self.config.on_quit()
		if self.metrics_logging_enabled:
			log_dir = dirname(self._get_metrics_json_path())
			log_file_path = join(log_dir, 'Metrics.log')
			self.metrics_backend.flush(log_file_path)
	@cached_property
	def app(self):
		result = Application([sys.argv[0]])
		result.setOrganizationName('fman.io')
		result.setOrganizationDomain('fman.io')
		result.setApplicationName('fman')
		result.setStyle(self.style)
		result.setPalette(self.palette)
		if self.app_icon:
			result.setWindowIcon(self.app_icon)
		result.aboutToQuit.connect(self.on_quit)
		return result
	@cached_property
	def app_icon(self):
		if not system.is_mac():
			return QIcon(self._get_resource('fman.ico'))
	@cached_property
	def command_callback(self):
		return CommandCallback(self.metrics)
	@cached_property
	def constants(self):
		with open(self._get_resource('constants.json'), 'r') as f:
			result = json.load(f)
		self._postprocess_constants(result)
		return result
	def _postprocess_constants(self, constants):
		filter_path = join(
			self._get_resource(), pardir, pardir, 'filters', 'filter-local.json'
		)
		with open(filter_path, 'r') as f:
			filter_ = json.load(f)
		for key, value in constants.items():
			if isinstance(value, str):
				for filter_key, filter_value in filter_.items():
					value = value.replace('${%s}' % filter_key, filter_value)
				constants[key] = value
	@cached_property
	def excepthook(self):
		return Excepthook(self.plugin_dirs, self.plugin_error_handler)
	@property
	def main_window(self):
		if self._main_window is None:
			self._main_window = MainWindow(
				self.app, self.help_menu_actions, self.theme, self.fs
			)
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
	@cached_property
	def help_menu_actions(self):
		if system.is_mac():
			def app_command(name):
				return lambda _: \
					self.plugin_support.run_application_command(name)
			def directory_pane_command(name):
				def result(_):
					active_pane = self.plugin_support.get_active_pane()
					if active_pane:
						active_pane.run_command(name)
				return result
			return [
				('Keyboard shortcuts', 'F1', app_command('help')),
				(
					'Command Palette', 'Ctrl+Shift+P',
					directory_pane_command('command_palette')
				),
				('Tutorial', '', app_command('tutorial'))
			]
		else:
			return []
	@cached_property
	def font_database(self):
		return FontDatabase()
	@cached_property
	def key_bindings(self):
		return KeyBindings()
	@cached_property
	def builtin_plugin(self):
		return BuiltinPlugin(
			self.plugin_error_handler, self.command_callback,
			self.key_bindings, self.tutorial
		)
	@cached_property
	def fs(self):
		file_systems = [DefaultFileSystem(), ZipFileSystem()]
		if PLATFORM == 'Windows':
			from fman.impl.model.fs import DrivesFileSystem
			file_systems.append(DrivesFileSystem())
		# Resolve the cyclic dependency MotherFileSystem <-> IconProvider:
		result = MotherFileSystem(file_systems, None)
		result._icon_provider = self._get_icon_provider(result)
		return result
	def _get_icon_provider(self, fs):
		try:
			qt_icon_provider = GnomeFileIconProvider()
		except GnomeNotAvailable:
			qt_icon_provider = QFileIconProvider()
		icons_dir = self._get_local_data_file('Cache', 'Icons')
		makedirs(icons_dir, exist_ok=True)
		return IconProvider(qt_icon_provider, fs, icons_dir)
	@cached_property
	def plugin_dirs(self):
		result = find_plugin_dirs(
			self._get_resource('Plugins'),
			join(DATA_DIRECTORY, 'Plugins', 'Third-party'),
			join(DATA_DIRECTORY, 'Plugins', 'User')
		)
		settings_plugin = result[-1]
		if not exists(settings_plugin):
			makedirs(settings_plugin)
		return result
	@cached_property
	def config(self):
		return Config(PLATFORM)
	@cached_property
	def splash_screen(self):
		return SplashScreen(self.main_window, self.app)
	@cached_property
	def tutorial(self):
		return Tutorial(
			self.main_window, self.app, self.command_callback, self.metrics
		)
	@cached_property
	def plugin_support(self):
		return PluginSupport(
			self.plugin_error_handler, self.command_callback, self.key_bindings,
			self.config, self.theme, self.font_database, self.builtin_plugin
		)
	@cached_property
	def plugin_error_handler(self):
		return PluginErrorHandler(self.app)
	@cached_property
	def controller(self):
		return Controller(
			self.window, self.plugin_support,
			self.nonexistent_shortcut_handler, self.metrics
		)
	@cached_property
	def nonexistent_shortcut_handler(self):
		settings = Settings(self._get_local_data_file('Dialogs.json'))
		return NonexistentShortcutHandler(
			self.main_window, settings, self.metrics
		)
	@cached_property
	def metrics(self):
		json_path = self._get_metrics_json_path()
		metrics = Metrics(
			json_path, self.metrics_backend, PLATFORM, self.fman_version
		)
		return AsynchronousMetrics(metrics)
	def _get_metrics_json_path(self):
		return self._get_local_data_file('Metrics.json')
	@cached_property
	def metrics_logging_enabled(self):
		return self._read_metrics_logging_enabled()
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
	@cached_property
	def metrics_backend(self):
		metrics_url = self.constants['server_url'] + '/metrics'
		backend = ServerBackend(metrics_url + '/users', metrics_url + '/events')
		if self.metrics_logging_enabled:
			backend = LoggingBackend(backend)
		return backend
	@cached_property
	def palette(self):
		result = QPalette()
		result.setColor(QPalette.Window, QColor(43, 43, 43))
		result.setColor(QPalette.WindowText, Qt.white)
		result.setColor(QPalette.Base, QColor(19, 19, 19))
		result.setColor(QPalette.AlternateBase, QColor(66, 64, 59))
		result.setColor(QPalette.ToolTipBase, QColor(19, 19, 19))
		result.setColor(QPalette.ToolTipText, Qt.white)
		result.setColor(QPalette.Light, QColor(0x49, 0x48, 0x3E))
		result.setColor(QPalette.Midlight, QColor(0x33, 0x33, 0x33))
		result.setColor(QPalette.Button, QColor(0x29, 0x29, 0x29))
		result.setColor(QPalette.Mid, QColor(0x25, 0x25, 0x25))
		result.setColor(QPalette.Dark, QColor(0x20, 0x20, 0x20))
		result.setColor(QPalette.Shadow, QColor(0x1d, 0x1d, 0x1d))
		result.setColor(QPalette.Text, Qt.white)
		result.setColor(
			QPalette.ButtonText, QColor(0xb6, 0xb3, 0xab)
		)
		result.setColor(QPalette.Link, Qt.white)
		result.setColor(QPalette.LinkVisited, Qt.white)
		return result
	@cached_property
	def user(self):
		json_path = self._get_local_data_file('User.json')
		try:
			with open(json_path, 'r') as f:
				data = json.load(f)
		except (IOError, ValueError):
			data = {}
		email = data.get('email', '')
		key = data.get('key', '')
		return User(email, key)
	@cached_property
	def is_licensed(self):
		return self.user.is_licensed(self.fman_version)
	@cached_property
	def main_window_palette(self):
		result = QPalette(self.palette)
		result.setColor(QPalette.Window, QColor(0x44, 0x44, 0x44))
		return result
	@cached_property
	def signal_wakeup_handler(self):
		return SignalWakeupHandler(self.app)
	@cached_property
	def session_manager(self):
		settings = Settings(self._get_local_data_file('Session.json'))
		return SessionManager(
			settings, self.fs, self.fman_version, self.is_licensed
		)
	@cached_property
	def theme(self):
		qss_files = [self._get_resource('styles.qss')]
		os_styles = self._get_resource('os_styles.qss')
		if exists(os_styles):
			qss_files.append(os_styles)
		return Theme(self.app, qss_files)
	@cached_property
	def style(self):
		return Style(QStyleFactory.create('Fusion'))
	@cached_property
	def updater(self):
		return None
	@cached_property
	def window(self):
		return Window()
	def _get_resource(self, *rel_path):
		res_dir = join(dirname(__file__), pardir, pardir, pardir, 'resources')
		os_dir = join(res_dir, PLATFORM.lower())
		os_path = normpath(join(os_dir, *rel_path))
		if exists(os_path):
			return os_path
		base_dir = join(res_dir, 'base')
		return normpath(join(base_dir, *rel_path))
	def _get_local_data_file(self, *rel_path):
		return join(DATA_DIRECTORY, 'Local', *rel_path)

class FrozenApplicationContext(ApplicationContext):
	def __init__(self):
		super().__init__()
		self._updater = None
	def init_logging(self):
		logging.basicConfig(level=logging.CRITICAL)
	@cached_property
	def updater(self):
		if self._should_auto_update():
			return MacUpdater(self.app)
	@cached_property
	def excepthook(self):
		return RollbarExcepthook(
			self.constants['rollbar_token'], self.constants['environment'],
			self.fman_version, self.plugin_dirs, self.plugin_error_handler
		)
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
	def _postprocess_constants(self, constants):
		pass