from fman import PLATFORM, Window, DirectoryPane
from fman.impl.plugins import PluginSupport, SETTINGS_PLUGIN_NAME
from fman.impl.plugins.config import Config
from fman.impl.plugins.key_bindings import KeyBindings
from fman.impl.plugins.mother_fs import MotherFileSystem
from fman_integrationtest import get_resource
from fman_integrationtest.impl.plugins import StubErrorHandler, \
	StubCommandCallback, StubTheme, StubFontDatabase, StubDirectoryPaneWidget
from os import mkdir
from os.path import join
from shutil import rmtree, copytree
from tempfile import mkdtemp
from unittest import TestCase

class PluginTest(TestCase):
	def setUp(self):
		self._shipped_plugins = mkdtemp()
		self._thirdparty_plugins = mkdtemp()
		self._user_plugins = mkdtemp()
		self._settings_plugin = join(self._user_plugins, SETTINGS_PLUGIN_NAME)
		mkdir(self._settings_plugin)
		self._shipped_plugin = join(self._shipped_plugins, 'Shipped')
		mkdir(self._shipped_plugin)
		self._thirdparty_plugin = \
			join(self._thirdparty_plugins, 'Simple Plugin')
		src_dir = get_resource('Simple Plugin')
		copytree(src_dir, self._thirdparty_plugin)
		config = Config(PLATFORM)
		self._error_handler = StubErrorHandler()
		self._command_callback = StubCommandCallback()
		key_bindings = KeyBindings()
		self._mother_fs = MotherFileSystem(None)
		theme = StubTheme()
		font_db = StubFontDatabase()
		self._plugin_support = PluginSupport(
			self._error_handler, self._command_callback, key_bindings,
			self._mother_fs, config, theme, font_db
		)
		self._plugin_support.load_plugin(self._shipped_plugin)
		self._plugin_support.load_plugin(self._thirdparty_plugin)
		self._plugin_support.load_plugin(self._settings_plugin)
		self._window = Window()
		left_pane = StubDirectoryPaneWidget(self._mother_fs)
		self._left_pane = DirectoryPane(self._window, left_pane)
		right_pane = StubDirectoryPaneWidget(self._mother_fs)
		self._right_pane = DirectoryPane(self._window, right_pane)
		self._plugin_support.on_pane_added(self._left_pane)
		self._plugin_support.on_pane_added(self._right_pane)
	def tearDown(self):
		rmtree(self._shipped_plugins)
		rmtree(self._thirdparty_plugins)
		rmtree(self._user_plugins)