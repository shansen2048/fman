from fman import PLATFORM
from fman.impl.plugin import PluginSupport, load_json, \
	write_differential_json, USER_PLUGIN_NAME, find_plugin_dirs
from fman_integrationtest import get_resource
from os import mkdir
from os.path import join, exists
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

class LoadJsonTest(TestCase):
	def test_nonexistent_file(self):
		self.assertIsNone(load_json('non-existent'))
	def test_dict(self):
		d = {'a': 1, 'b': 1}
		json_path = self._save_to_json(d)
		self.assertEqual(d, load_json(json_path))
	def test_dict_multiple_files(self):
		d1 = {'a': 1, 'b': 1}
		d2 = {'b': 2, 'c': 2}
		json1 = self._save_to_json(d1)
		json2 = self._save_to_json(d2)
		self.assertEqual({'a': 1, 'b': 2, 'c': 2}, load_json(json1, json2))
	def test_list(self):
		l = [1, 2]
		json_path = self._save_to_json(l)
		self.assertEqual(l, load_json(json_path))
	def test_list_multiple_files(self):
		l1 = [1, 2]
		l2 = [3]
		json1 = self._save_to_json(l1)
		json2 = self._save_to_json(l2)
		self.assertEqual(l2 + l1, load_json(json1, json2))
	def test_string(self):
		string = 'test'
		json_path = self._save_to_json(string)
		self.assertEqual(string, load_json(json_path))
	def test_string_multiple_files(self):
		s1 = 'test1'
		s2 = 'test2'
		json1 = self._save_to_json(s1)
		json2 = self._save_to_json(s2)
		self.assertEqual(s2, load_json(json2, json1))
	def test_multiple_files_first_does_not_exist(self):
		value = {'a': 1}
		json_path = self._save_to_json(value)
		self.assertEqual(value, load_json('non-existent', json_path))
	def setUp(self):
		self.temp_dir = mkdtemp()
		self.num_files = 0
	def tearDown(self):
		rmtree(self.temp_dir)
	def _save_to_json(self, value):
		json_path = join(self.temp_dir, '%d.json' % self.num_files)
		with open(json_path, 'w') as f:
			json.dump(value, f)
		self.num_files += 1
		return json_path

class WriteDifferentialJsonTest(TestCase):
	def test_dict(self):
		self._check_write({'a': 1})
	def test_list(self):
		self._check_write([1, 2])
	def test_string(self):
		self._check_write("hello!")
	def test_int(self):
		self._check_write(3)
	def test_bool(self):
		self._check_write(True)
	def test_float(self):
		self._check_write(4.5)
	def test_overwrite_dict_value(self):
		d = {'a': 1, 'b': 1}
		with open(self._json_file(), 'w') as f:
			json.dump(d, f)
		d['b'] = 2
		d['c'] = 3
		self._check_write(d)
	def test_dict_incremental_update(self):
		d = {'a': 1, 'b': 1}
		with open(self._json_file(0), 'w') as f:
			json.dump(d, f)
		d['b'] = 2
		d['c'] = 3
		write_differential_json(d, self._json_file(0), self._json_file(1))
		with open(self._json_file(1), 'r') as f:
			self.assertEqual({'b': 2, 'c': 3}, json.load(f))
	def test_extend_list(self):
		write_differential_json([1, 2], self._json_file())
		self._check_write([1, 2, 3])
	def test_update_list(self):
		json1 = self._json_file(0)
		json2 = self._json_file(1)
		with open(json1, 'w') as f:
			json.dump([2, 3], f)
		with open(json2, 'w') as f:
			json.dump([1], f)
		write_differential_json([0, 1, 2, 3], json1, json2)
		with open(json2, 'r') as f:
			self.assertEqual([0, 1], json.load(f))
	def test_type_change_raises(self):
		write_differential_json(1, self._json_file())
		with self.assertRaises(ValueError):
			write_differential_json({'x': 1}, self._json_file())
	def test_update_unmodifiable_list_parts_raises(self):
		json1 = self._json_file(0)
		json2 = self._json_file(1)
		with open(json1, 'w') as f:
			json.dump([1], f)
		with open(json2, 'w') as f:
			json.dump([2], f)
		with self.assertRaises(ValueError):
			write_differential_json(json1, json2)
	def test_no_change(self):
		json1 = self._json_file(0)
		l = [0, 1]
		with open(json1, 'w') as f:
			json.dump(l, f)
		json2 = self._json_file(1)
		write_differential_json(l, json1, json2)
		self.assertFalse(exists(json2))
	def setUp(self):
		self.temp_dir = mkdtemp()
	def tearDown(self):
		rmtree(self.temp_dir)
	def _check_write(self, obj):
		write_differential_json(obj, self._json_file())
		self.assertEqual(obj, load_json(self._json_file()))
	def _json_file(self, i=0):
		return join(self.temp_dir, '%d.json' % i)