from fman import PLATFORM, Window, DirectoryPane
from fman.impl.plugins import PluginSupport, SETTINGS_PLUGIN_NAME
from fman.impl.plugins.config import Config
from fman.impl.plugins.key_bindings import KeyBindings
from fman_integrationtest import get_resource
from fman_integrationtest.impl.plugins import StubErrorHandler, \
	StubCommandCallback, StubTheme, StubFontDatabase, StubMotherFileSystem
from os import mkdir
from os.path import join
from shutil import rmtree, copytree
from tempfile import mkdtemp
from time import time, sleep
from unittest import TestCase

import json

class PluginSupportTest(TestCase):
	def test_load_json_default(self):
		d = {}
		self.assertIs(d, self._plugin_support.load_json('Nonexistent.json', d))
		self.assertIs(d, self._plugin_support.load_json('Nonexistent.json'))
	def test_load_json_dict(self):
		with open(join(self._shipped_plugin, 'Test.json'), 'w') as f:
			json.dump({'a': 1, 'b': 2, 'c': 3}, f)
		with open(join(self._thirdparty_plugin, 'Test.json'), 'w') as f:
			json.dump({'b': 'overwritten', 'installed': 1}, f)
		with open(join(self._settings_plugin, 'Test.json'), 'w') as f:
			json.dump({'c': 'overwritten', 'user': 1}, f)
		self.assertEqual(
			{
				'a': 1, 'b': 'overwritten', 'c': 'overwritten',
				'installed': 1, 'user': 1
			},
			self._plugin_support.load_json('Test.json'),
			'Settings plugin should overwrite installed should overwrite '
			'shipped.'
		)
	def test_load_json_list(self):
		with open(join(self._shipped_plugin, 'Test.json'), 'w') as f:
			json.dump(['shipped'], f)
		with open(join(self._thirdparty_plugin, 'Test.json'), 'w') as f:
			json.dump(['installed'], f)
		with open(join(self._settings_plugin, 'Test.json'), 'w') as f:
			json.dump(['user'], f)
		self.assertEqual(
			['user', 'installed', 'shipped'],
			self._plugin_support.load_json('Test.json')
		)
	def test_load_json_platform_overwrites(self):
		with open(join(self._shipped_plugin, 'Test.json'), 'w') as f:
			json.dump({'a': 1, 'b': 2}, f)
		json_platform = 'Test (%s).json' % PLATFORM
		with open(join(self._shipped_plugin, json_platform), 'w') as f:
			json.dump({'b': 'overwritten'}, f)
		self.assertEqual(
			{'a': 1, 'b': 'overwritten'},
			self._plugin_support.load_json('Test.json')
		)
	def test_load_json_caches(self):
		with open(join(self._shipped_plugin, 'Test.json'), 'w') as f:
			json.dump({'a': 1}, f)
		d = self._plugin_support.load_json('Test.json')
		self.assertIs(d, self._plugin_support.load_json('Test.json'))
	def test_save_json(self):
		d = {'test_save_json': 1}
		self._plugin_support.save_json('Test.json', d)
		json_platform = join(self._settings_plugin, 'Test (%s).json' % PLATFORM)
		with open(json_platform, 'r') as f:
			self.assertEqual(d, json.load(f))
	def test_key_bindings(self, timeout_secs=1):
		key_bindings = self._plugin_support.get_sanitized_key_bindings()
		self.assertEqual(2, len(key_bindings))
		first, second = key_bindings
		self.assertEqual({
			'keys': ['Enter'],
			'command': 'test_command',
			'args': {
				'success': True
			}
		}, first)
		# Can do this now because sys.path has been extended by `Plugin#load()`:
		from simple_plugin import TestCommand
		self.assertFalse(TestCommand.RAN, 'Sanity check')
		try:
			self._plugin_support.run_application_command(
				'test_command', {'ran': True}
			)
			end_time = time() + timeout_secs
			while time() < end_time:
				if TestCommand.RAN:
					# Success.
					break
				else:
					sleep(.1)
			else:
				self.fail("TestCommand didn't run.")
		finally:
			TestCommand.RAN = False
		self.assertEqual({
			'keys': ['Space'],
			'command': 'command_raising_error'
		}, second)
		# Should not raise an exception:
		self._left_pane.run_command('command_raising_error')
		self.assertEqual(
			["Command 'CommandRaisingError' raised exception."],
			self._error_handler.error_messages
		)
	def test_on_path_changed_error(self):
		self._left_pane._broadcast('on_path_changed')
		self.assertEqual(
			["DirectoryPaneListener 'ListenerRaisingError' raised error."],
			self._error_handler.error_messages
		)
	def test_on_doubleclicked_error(self):
		self._left_pane._broadcast('on_doubleclicked', self._settings_plugin)
		self.assertEqual(
			["DirectoryPaneListener 'ListenerRaisingError' raised error."],
			self._error_handler.error_messages
		)
	def test_on_name_edited_error(self):
		self._left_pane._broadcast(
			'on_name_edited', self._settings_plugin, 'New name'
		)
		self.assertEqual(
			["DirectoryPaneListener 'ListenerRaisingError' raised error."],
			self._error_handler.error_messages
		)
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
		mother_fs = StubMotherFileSystem()
		theme = StubTheme()
		font_db = StubFontDatabase()
		self._plugin_support = PluginSupport(
			self._error_handler, self._command_callback, key_bindings,
			mother_fs, config, theme, font_db
		)
		self._plugin_support.load_plugin(self._shipped_plugin)
		self._plugin_support.load_plugin(self._thirdparty_plugin)
		self._plugin_support.load_plugin(self._settings_plugin)
		self._window = Window()
		self._left_pane = DirectoryPane(self._window, None)
		self._right_pane = DirectoryPane(self._window, None)
		self._plugin_support.on_pane_added(self._left_pane)
		self._plugin_support.on_pane_added(self._right_pane)
	def tearDown(self):
		rmtree(self._shipped_plugins)
		rmtree(self._thirdparty_plugins)
		rmtree(self._user_plugins)