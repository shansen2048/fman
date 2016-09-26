from fman import DirectoryPaneCommand
from fman.impl.controller import KeyBinding
from fman.util.system import get_canonical_os_name
from glob import glob
from importlib import import_module
from inspect import getmro
from os import listdir, makedirs
from os.path import join, isdir, splitext, basename, dirname
from PyQt5.QtGui import QKeySequence

import json
import re
import sys

class PluginSupport:

	USER_PLUGIN_NAME = 'User'

	def __init__(self, user_plugins_dir, shipped_plugins_dir, controller):
		self.user_plugins_dir = user_plugins_dir
		self.shipped_plugins_dir = shipped_plugins_dir
		self.controller = controller
		self.plugins = []
		self.commands = {}
	def initialize(self):
		self._load_plugins()
		self.controller.key_bindings.extend(self._parse_key_bindings())
	def get_user_plugin(self):
		return self.plugins[0]
	def load_json(self, name):
		return load_json(*self._get_json_paths(name))
	def write_json(self, value, name):
		return write_differential_json(value, *self._get_json_paths(name))
	def _get_json_paths(self, name):
		plugin_dirs = [plugin.path for plugin in self.plugins]
		base, ext = splitext(name)
		platform_title = self._get_platform_title()
		platform_specific_name = '%s (%s)%s' % (base, platform_title, ext)
		result = []
		for plugin_dir in plugin_dirs:
			result.append(join(plugin_dir, platform_specific_name))
			result.append(join(plugin_dir, name))
		return result
	def _load_plugins(self):
		for plugin_dir in self._find_plugins():
			plugin = Plugin(plugin_dir)
			plugin.load()
			self.plugins.append(plugin)
			self.commands.update(plugin.commands)
	def _find_plugins(self):
		result = [join(self.user_plugins_dir, self.USER_PLUGIN_NAME)]
		try:
			user_plugins = listdir(self.user_plugins_dir)
		except FileNotFoundError:
			user_plugins = []
		for plugin in user_plugins:
			plugin_path = join(self.user_plugins_dir, plugin)
			if plugin != self.USER_PLUGIN_NAME and isdir(plugin_path):
				result.append(plugin_path)
		for plugin in listdir(self.shipped_plugins_dir):
			plugin_path = join(self.shipped_plugins_dir, plugin)
			if isdir(plugin_path):
				result.append(plugin_path)
		return result
	def _parse_key_bindings(self):
		result = []
		key_bindings = self.load_json('Key Bindings.json')
		for binding in key_bindings:
			result.append(self._parse_key_binding(binding))
		return result
	def _parse_key_binding(self, json_obj):
		key_sequence = QKeySequence(json_obj['keys'][0])
		command = self.commands[json_obj['command']]
		args = json_obj.get('args', {})
		return KeyBinding(key_sequence, command, args)
	def _get_platform_title(self):
		result = get_canonical_os_name().title()
		if result == 'Osx':
			result = 'OSX'
		return result

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
			for k, v in next_value.items():
				if k not in result:
					result[k] = v
		elif isinstance(next_value, list):
			result.extend(next_value)
	return result

def write_differential_json(obj, path, *paths):
	old_obj = load_json(path, *paths)
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
			base = load_json(*paths) or {}
			difference = {
				key: value for key, value in obj.items()
				if key not in base or base[key] != value
			}
		elif isinstance(obj, list):
			changeable = load_json(path) or []
			remainder = old_obj[len(changeable):]
			if remainder:
				if obj[-len(remainder):] != remainder:
					raise ValueError(
						"It's not possible to update list items in paths %r." %
						((path,) + paths,)
					)
				difference = obj[:-len(remainder)]
			else:
				difference = obj
		else:
			difference = obj
	makedirs(dirname(path), exist_ok=True)
	with open(path, 'w') as f:
		json.dump(difference, f)