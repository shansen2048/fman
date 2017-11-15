from fman import PLATFORM, Window, DirectoryPane
from fman.impl.plugins import PluginSupport, SETTINGS_PLUGIN_NAME
from fman.impl.plugins.config import Config
from fman.impl.plugins.key_bindings import KeyBindings
from fman_integrationtest import get_resource
from fman_integrationtest.impl.plugins import StubErrorHandler, \
	StubCommandCallback, StubTheme, StubFontDatabase
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
		self.assertIs(d, self.plugin_support.load_json('Nonexistent.json', d))
		self.assertIs(d, self.plugin_support.load_json('Nonexistent.json'))
	def test_load_json_dict(self):
		with open(join(self.shipped_plugin, 'Test.json'), 'w') as f:
			json.dump({'a': 1, 'b': 2, 'c': 3}, f)
		with open(join(self.thirdparty_plugin, 'Test.json'), 'w') as f:
			json.dump({'b': 'overwritten', 'installed': 1}, f)
		with open(join(self.settings_plugin, 'Test.json'), 'w') as f:
			json.dump({'c': 'overwritten', 'user': 1}, f)
		self.assertEqual(
			{
				'a': 1, 'b': 'overwritten', 'c': 'overwritten',
				'installed': 1, 'user': 1
			},
			self.plugin_support.load_json('Test.json'),
			'Settings plugin should overwrite installed should overwrite '
			'shipped.'
		)
	def test_load_json_list(self):
		with open(join(self.shipped_plugin, 'Test.json'), 'w') as f:
			json.dump(['shipped'], f)
		with open(join(self.thirdparty_plugin, 'Test.json'), 'w') as f:
			json.dump(['installed'], f)
		with open(join(self.settings_plugin, 'Test.json'), 'w') as f:
			json.dump(['user'], f)
		self.assertEqual(
			['user', 'installed', 'shipped'],
			self.plugin_support.load_json('Test.json')
		)
	def test_load_json_platform_overwrites(self):
		with open(join(self.shipped_plugin, 'Test.json'), 'w') as f:
			json.dump({'a': 1, 'b': 2}, f)
		json_platform = 'Test (%s).json' % PLATFORM
		with open(join(self.shipped_plugin, json_platform), 'w') as f:
			json.dump({'b': 'overwritten'}, f)
		self.assertEqual(
			{'a': 1, 'b': 'overwritten'},
			self.plugin_support.load_json('Test.json')
		)
	def test_load_json_caches(self):
		with open(join(self.shipped_plugin, 'Test.json'), 'w') as f:
			json.dump({'a': 1}, f)
		d = self.plugin_support.load_json('Test.json')
		self.assertIs(d, self.plugin_support.load_json('Test.json'))
	def test_save_json(self):
		d = {'test_save_json': 1}
		self.plugin_support.save_json('Test.json', d)
		json_platform = join(self.settings_plugin, 'Test (%s).json' % PLATFORM)
		with open(json_platform, 'r') as f:
			self.assertEqual(d, json.load(f))
	def test_key_bindings(self, timeout_secs=1):
		key_bindings = self.plugin_support.get_sanitized_key_bindings()
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
			self.plugin_support.run_application_command(
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
		self.left_pane.run_command('command_raising_error')
		self.assertEqual(
			["Command 'CommandRaisingError' raised exception."],
			self.error_handler.error_messages
		)
	def test_on_path_changed_error(self):
		self.left_pane._broadcast('on_path_changed')
		self.assertEqual(
			["DirectoryPaneListener 'ListenerRaisingError' raised error."],
			self.error_handler.error_messages
		)
	def test_on_doubleclicked_error(self):
		self.left_pane._broadcast('on_doubleclicked', self.settings_plugin)
		self.assertEqual(
			["DirectoryPaneListener 'ListenerRaisingError' raised error."],
			self.error_handler.error_messages
		)
	def test_on_name_edited_error(self):
		self.left_pane._broadcast(
			'on_name_edited', self.settings_plugin, 'New name'
		)
		self.assertEqual(
			["DirectoryPaneListener 'ListenerRaisingError' raised error."],
			self.error_handler.error_messages
		)
	def setUp(self):
		self.shipped_plugins = mkdtemp()
		self.thirdparty_plugins = mkdtemp()
		self.user_plugins = mkdtemp()
		self.settings_plugin = join(self.user_plugins, SETTINGS_PLUGIN_NAME)
		mkdir(self.settings_plugin)
		self.shipped_plugin = join(self.shipped_plugins, 'Shipped')
		mkdir(self.shipped_plugin)
		self.thirdparty_plugin = join(self.thirdparty_plugins, 'Simple Plugin')
		src_dir = get_resource('Simple Plugin')
		copytree(src_dir, self.thirdparty_plugin)
		config = Config(PLATFORM)
		self.error_handler = StubErrorHandler()
		self.command_callback = StubCommandCallback()
		key_bindings = KeyBindings()
		theme = StubTheme()
		font_db = StubFontDatabase()
		self.plugin_support = PluginSupport(
			self.error_handler, self.command_callback, key_bindings, None,
			config, theme, font_db
		)
		self.plugin_support.load_plugin(self.shipped_plugin)
		self.plugin_support.load_plugin(self.thirdparty_plugin)
		self.plugin_support.load_plugin(self.settings_plugin)
		self.window = Window()
		self.left_pane = DirectoryPane(self.window, None)
		self.right_pane = DirectoryPane(self.window, None)
		self.plugin_support.on_pane_added(self.left_pane)
		self.plugin_support.on_pane_added(self.right_pane)
	def tearDown(self):
		rmtree(self.shipped_plugins)
		rmtree(self.thirdparty_plugins)
		rmtree(self.user_plugins)