from fman import DirectoryPaneCommand, platform
from fman.impl.controller import KeyBinding
from fman.util import listdir_absolute
from glob import glob
from importlib import import_module
from inspect import getmro
from os import makedirs
from os.path import join, isdir, splitext, basename, dirname
from PyQt5.QtGui import QKeySequence

import json
import re
import sys

class PluginSupport:

	USER_PLUGIN_NAME = 'User'

	def __init__(self, shipped_plugins_dir, installed_plugins_dir, controller):
		self.shipped_plugins_dir = shipped_plugins_dir
		self.installed_plugins_dir = installed_plugins_dir
		self.controller = controller
		self.plugins = []
		self.commands = {}
	def initialize(self):
		self._load_plugins()
		self.controller.key_bindings.extend(self._load_key_bindings())
	def get_user_plugin(self):
		return self.plugins[0]
	def load_json(self, name):
		return load_json(*self._get_json_paths(name))
	def write_json(self, value, name):
		return write_differential_json(value, *self._get_json_paths(name))
	def _get_json_paths(self, name):
		plugin_dirs = [plugin.path for plugin in self.plugins]
		base, ext = splitext(name)
		platform_specific_name = '%s (%s)%s' % (base, platform(), ext)
		result = []
		for plugin_dir in plugin_dirs:
			result.append(join(plugin_dir, name))
			result.append(join(plugin_dir, platform_specific_name))
		return result
	def _load_plugins(self):
		for plugin_dir in self._find_plugins():
			plugin = Plugin(plugin_dir)
			plugin.load()
			self.plugins.append(plugin)
			self.commands.update(plugin.commands)
	def _find_plugins(self):
		shipped_plugins = self._list_plugins(self.shipped_plugins_dir)
		installed_plugins = [
			plugin for plugin in self._list_plugins(self.installed_plugins_dir)
		 	if basename(plugin) != self.USER_PLUGIN_NAME
		]
		user_plugin = join(self.installed_plugins_dir, self.USER_PLUGIN_NAME)
		return shipped_plugins + installed_plugins + [user_plugin]
	def _list_plugins(self, dir_path):
		try:
			return list(filter(isdir, listdir_absolute(dir_path)))
		except FileNotFoundError:
			return []
	def _load_key_bindings(self):
		result = []
		key_bindings = self.load_json('Key Bindings.json') or []
		for binding in key_bindings:
			result.append(self._parse_key_binding(binding))
		return result
	def _parse_key_binding(self, json_obj):
		key_sequence = QKeySequence(json_obj['keys'][0])
		command = self.commands[json_obj['command']]
		args = json_obj.get('args', {})
		return KeyBinding(key_sequence, command, args)

class Plugin:
	def __init__(self, dir_path):
		self.path = dir_path
		self.commands = {}
	def load(self):
		sys.path.append(self.path)
		for cls in self._get_command_classes():
			self.commands[self._get_command_name(cls.__name__)] = cls
	def _get_command_classes(self):
		result = []
		for py_file in glob(join(self.path, '*.py')):
			module_name, _ = splitext(basename(py_file))
			module = import_module(module_name)
			for member_name in dir(module):
				member = getattr(module, member_name)
				try:
					mro = getmro(member)
				except Exception as not_a_class:
					continue
				if DirectoryPaneCommand in mro:
					result.append(member)
		return result
	def _get_command_name(self, command_class_name):
		return re.sub(r'([a-z])([A-Z])', r'\1_\2', command_class_name).lower()

def load_json(*paths):
	result = None
	for path in paths:
		try:
			with open(path, 'r') as f:
				next_value = json.load(f)
		except FileNotFoundError:
			continue
		if result is None:
			result = type(next_value)(next_value)
			continue
		if type(next_value) != type(result):
			raise ValueError(
				'Cannot join types %s and %s.' %
				(type(next_value).__name__, type(result).__name__)
			)
		if isinstance(next_value, dict):
			result.update(next_value)
		elif isinstance(next_value, list):
			result = next_value + result
	return result

def write_differential_json(obj, *paths):
	dest_path = paths[-1]
	old_obj = load_json(*paths)
	if old_obj is None:
		difference = obj
	else:
		if type(obj) != type(old_obj):
			raise ValueError(
				'Cannot overwrite value of type %s with different type %s.' %
				(type(old_obj).__name__, type(obj).__name__)
			)
		if isinstance(obj, dict):
			deleted = [key for key in old_obj if key not in obj]
			if deleted:
				raise ValueError('Deleting keys %r is not supported.' % deleted)
			base = load_json(*paths[:-1]) or {}
			difference = {
				key: value for key, value in obj.items()
				if key not in base or base[key] != value
			}
		elif isinstance(obj, list):
			changeable = load_json(dest_path) or []
			remainder = old_obj[len(changeable):]
			if remainder:
				if obj[-len(remainder):] != remainder:
					raise ValueError(
						"It's not possible to update list items in paths %r." %
						(paths,)
					)
				difference = obj[:-len(remainder)]
			else:
				difference = obj
		else:
			difference = obj
	makedirs(dirname(dest_path), exist_ok=True)
	with open(dest_path, 'w') as f:
		json.dump(difference, f)