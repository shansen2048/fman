from fman.impl.plugin import load_json, write_differential_json, Plugin
from os.path import join
from shutil import rmtree
from tempfile import mkdtemp
from unittest import TestCase

import json

class PluginTest(TestCase):
	def test_single_letter(self):
		self.assertEqual('c', self._get_command_name('C'))
	def test_single_word(self):
		self.assertEqual('copy', self._get_command_name('Copy'))
	def test_two_words(self):
		self.assertEqual(
			'open_terminal', self._get_command_name('OpenTerminal')
		)
	def test_three_words(self):
		self.assertEqual(
			'move_cursor_up', self._get_command_name('MoveCursorUp')
		)
	def test_two_consecutive_upper_case_chars(self):
		self.assertEqual('get_url', self._get_command_name('GetURL'))
	def _get_command_name(self, command_class_name):
		return Plugin('dummy')._get_command_name(command_class_name)

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
		self.assertEqual({'a': 1, 'b': 2, 'c': 2}, load_json(json2, json1))
	def test_list(self):
		l = [1, 2]
		json_path = self._save_to_json(l)
		self.assertEqual(l, load_json(json_path))
	def test_list_multiple_files(self):
		l1 = [1, 2]
		l2 = [3]
		json1 = self._save_to_json(l1)
		json2 = self._save_to_json(l2)
		self.assertEqual(l1 + l2, load_json(json1, json2))
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
	def _check_write(self, obj):
		write_differential_json(obj, self.json_file())
		self.assertEqual(obj, load_json(self.json_file()))
	def test_overwrite_dict_value(self):
		d = {'a': 1, 'b': 1}
		with open(self.json_file(), 'w') as f:
			json.dump(d, f)
		d['b'] = 2
		d['c'] = 3
		self._check_write(d)
	def test_dict_incremental_update(self):
		d = {'a': 1, 'b': 1}
		with open(self.json_file(1), 'w') as f:
			json.dump(d, f)
		d['b'] = 2
		d['c'] = 3
		write_differential_json(d, self.json_file(0), self.json_file(1))
		with open(self.json_file(0), 'r') as f:
			self.assertEqual({'b': 2, 'c': 3}, json.load(f))
	def test_extend_list(self):
		write_differential_json([1, 2], self.json_file())
		self._check_write([1, 2, 3])
	def test_update_list(self):
		json1 = self.json_file(0)
		json2 = self.json_file(1)
		with open(json1, 'w') as f:
			json.dump([1], f)
		with open(json2, 'w') as f:
			json.dump([2, 3], f)
		write_differential_json([0, 1, 2, 3], json1, json2)
		with open(json1, 'r') as f:
			self.assertEqual([0, 1], json.load(f))
	def test_type_change_raises(self):
		write_differential_json(1, self.json_file())
		with self.assertRaises(ValueError):
			write_differential_json({'x': 1}, self.json_file())
	def test_update_unmodifiable_list_parts_raises(self):
		json1 = self.json_file(0)
		json2 = self.json_file(1)
		with open(json1, 'w') as f:
			json.dump([1], f)
		with open(json2, 'w') as f:
			json.dump([2], f)
		with self.assertRaises(ValueError):
			write_differential_json([0, 1], json1, json2)
	def json_file(self, i=0):
		return join(self.temp_dir, '%d.json' % i)
	def setUp(self):
		self.temp_dir = mkdtemp()
	def tearDown(self):
		rmtree(self.temp_dir)