from fman import PLATFORM
from fman.impl.plugins import ExternalPlugin
from fman.impl.plugins.config import Config
from fman.impl.plugins.key_bindings import KeyBindings
from fman_integrationtest import get_resource
from fman_integrationtest.impl.plugins import StubErrorHandler, \
	StubCommandCallback, StubTheme, StubFontDatabase
from os.path import join
from unittest import TestCase

import json
import sys

class ExternalPluginTest(TestCase):
	def test_load(self):
		self._plugin.load()
		with open(join(self._plugin_dir, 'Key Bindings.json'), 'r') as f:
			bindings = json.load(f)
		self.assertEquals(bindings, self._config.load_json('Key Bindings.json'))
		plugin_font = join(self._plugin_dir, 'Open Sans.ttf')
		self.assertEquals([plugin_font], self._font_database.loaded_fonts)
		theme_css = join(self._plugin_dir, 'Theme.css')
		self.assertEquals([theme_css], self._theme.loaded_css_files)
		self.assertIn(self._plugin_dir, sys.path)
		self.assertIn('test_command', self._plugin.get_application_commands())
		self.assertIn(
			'command_raising_error', self._plugin.get_directory_pane_commands()
		)
		from simple_plugin import ListenerRaisingError
		self.assertIn(
			ListenerRaisingError, self._plugin._directory_pane_listeners
		)
		self.assertEquals(bindings, self._key_bindings.get_sanitized_bindings())
	def test_unload(self):
		self.test_load()
		self._plugin.unload()
		self.assertEquals([], self._key_bindings.get_sanitized_bindings())
		self.assertEquals([], self._plugin._directory_pane_listeners)
		self.assertEquals({}, self._plugin.get_directory_pane_commands())
		self.assertEquals({}, self._plugin.get_application_commands())
		self.assertNotIn(self._plugin_dir, sys.path)
		self.assertEquals([], self._theme.loaded_css_files)
		self.assertEquals([], self._font_database.loaded_fonts)
		self.assertIsNone(self._config.load_json('Key Bindings.json'))
	def setUp(self):
		super().setUp()
		self._sys_path_before = list(sys.path)
		self._plugin_dir = get_resource('Simple Plugin')
		self._error_handler = StubErrorHandler()
		self._command_callback = StubCommandCallback()
		self._key_bindings = KeyBindings()
		self._config = Config(PLATFORM)
		self._font_database = StubFontDatabase()
		self._theme = StubTheme()
		self._plugin = ExternalPlugin(
			self._error_handler, self._command_callback, self._key_bindings,
			self._plugin_dir, self._config, self._theme, self._font_database
		)
	def tearDown(self):
		sys.path = self._sys_path_before
		super().tearDown()