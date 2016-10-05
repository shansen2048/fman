from fman import platform
from fman.impl import MainWindow
from fman.impl.metrics import Metrics
from fman.impl.controller import Controller
from fman.impl.excepthook import Excepthook
from fman.impl.plugin import PluginSupport
from fman.impl.session import SessionManager
from fman.impl.view import Style
from fman.updater import EskyUpdater, MacUpdater
from fman.util import system
from os import getenv, rename
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
		self._excepthook = None
		self._main_window = None
		self._controller = None
		self._plugin_support = None
		self._session_manager = None
		self._stylesheet = None
		self._style = None
		self._metrics = None
	def initialize(self):
		self.excepthook.install()
		self.metrics.initialize()
		self.excepthook.user_id = self.metrics.user_id
		self.metrics.super_properties.update({
			'$os': platform(), '$app_version': self.constants['version']
		})
		self.metrics.track('Started fman')
		# Ensure QApplication is initialized before anything else Qt-related:
		_ = self.app
		self._load_fonts()
		self.plugin_support.initialize()
		self.session_manager.on_startup(self.main_window)
		if self.updater:
			self.updater.start()
		# TODO: Remove this migration some time after mid October 2016:
		self._migrate_versions_lte_0_0_4()
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
			self._main_window = MainWindow(self.controller)
			self._main_window.pane_added.connect(
				self.plugin_support.on_pane_added
			)
			self._main_window.closeEvent = \
				lambda _: self.session_manager.on_close(self.main_window)
		return self._main_window
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
	def controller(self):
		if self._controller is None:
			self._controller = Controller(self.plugin_support, self.metrics)
		return self._controller
	@property
	def plugin_support(self):
		if self._plugin_support is None:
			shipped_plugins = self.get_resource('Plugins')
			installed_plugins = join(get_data_dir(), 'Plugins')
			self._plugin_support = \
				PluginSupport(shipped_plugins, installed_plugins)
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
	def _postprocess_constants(self):
		pass