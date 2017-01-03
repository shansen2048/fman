from fman import PLATFORM
from fman.impl.plugin import PluginSupport, USER_PLUGIN_NAME, find_plugin_dirs
from fman_integrationtest import get_resource
from os import mkdir
from os.path import join
from shutil import rmtree, copytree
from tempfile import mkdtemp
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
		with open(join(self.installed_plugin, 'Test.json'), 'w') as f:
			json.dump({'b': 'overwritten', 'installed': 1}, f)
		with open(join(self.user_plugin, 'Test.json'), 'w') as f:
			json.dump({'c': 'overwritten', 'user': 1}, f)
		self.assertEqual(
			{
				'a': 1, 'b': 'overwritten', 'c': 'overwritten',
				'installed': 1, 'user': 1
			},
			self.plugin_support.load_json('Test.json'),
			'User plugin should overwrite installed should overwrite shipped.'
		)
	def test_load_json_list(self):
		with open(join(self.shipped_plugin, 'Test.json'), 'w') as f:
			json.dump(['shipped'], f)
		with open(join(self.installed_plugin, 'Test.json'), 'w') as f:
			json.dump(['installed'], f)
		with open(join(self.user_plugin, 'Test.json'), 'w') as f:
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
		json_platform = join(self.user_plugin, 'Test (%s).json' % PLATFORM)
		with open(json_platform, 'r') as f:
			self.assertEqual(d, json.load(f))
	def test_find_plugins(self):
		self.assertEqual(
			self.plugin_dirs,
			find_plugin_dirs(self.shipped_plugins, self.installed_plugins)
		)
	def test_key_bindings(self):
		pane = self.left_pane
		key_bindings = self.plugin_support.get_key_bindings_for_pane(pane)
		self.assertEqual(2, len(key_bindings))
		test_command, command_raising_error = key_bindings
		self.assertEqual(["Enter"], test_command.keys)
		self.assertEqual(["Space"], command_raising_error.keys)
		for binding in key_bindings:
			self.assertIs(pane, binding.command.wrapped_command.pane)
		self.assertEqual(True, test_command.command(success=True))
		# Should not raise an exception:
		command_raising_error.command()
		self.assertEqual(
			["Command 'CommandRaisingError' raised exception."],
			self.error_handler.error_messages
		)
	def test_on_path_changed_error(self):
		self.plugin_support.on_path_changed(self.left_pane)
		self.assertEqual(
			["DirectoryPaneListener 'ListenerRaisingError' raised error."],
			self.error_handler.error_messages
		)
	def test_on_doubleclicked_error(self):
		self.plugin_support.on_doubleclicked(self.left_pane, self.user_plugin)
		self.assertEqual(
			["DirectoryPaneListener 'ListenerRaisingError' raised error."],
			self.error_handler.error_messages
		)
	def test_on_on_name_edited_error(self):
		self.plugin_support.on_name_edited(
			self.left_pane, self.user_plugin, 'New name'
		)
		self.assertEqual(
			["DirectoryPaneListener 'ListenerRaisingError' raised error."],
			self.error_handler.error_messages
		)
	def setUp(self):
		self.shipped_plugins = mkdtemp()
		self.installed_plugins = mkdtemp()
		self.user_plugin = join(self.installed_plugins, USER_PLUGIN_NAME)
		mkdir(self.user_plugin)
		self.shipped_plugin = join(self.shipped_plugins, 'Shipped')
		mkdir(self.shipped_plugin)
		self.installed_plugin = join(self.installed_plugins, 'Simple Plugin')
		src_dir = get_resource('PluginSupportTest/Simple Plugin')
		copytree(src_dir, self.installed_plugin)
		self.plugin_dirs = \
			[self.shipped_plugin, self.installed_plugin, self.user_plugin]
		self.error_handler = StubErrorHandler()
		self.plugin_support = \
			PluginSupport(self.plugin_dirs, self.error_handler)
		self.plugin_support.initialize()
		self.left_pane = StubDirectoryPane()
		self.right_pane = StubDirectoryPane()
		self.plugin_support.on_pane_added(self.left_pane)
		self.plugin_support.on_pane_added(self.right_pane)
	def tearDown(self):
		rmtree(self.shipped_plugins)
		rmtree(self.installed_plugins)

class StubErrorHandler:
	def __init__(self):
		self.error_messages = []
	def report(self, message):
		self.error_messages.append(message)

class StubSignal:
	def connect(self, slot):
		pass

class StubDirectoryPane:
	path_changed = StubSignal()