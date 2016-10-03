from collections import namedtuple
from fman import DirectoryPaneCommand, platform
from fman.util import listdir_absolute
from glob import glob
from importlib.machinery import SourceFileLoader
from inspect import getmro
from os import makedirs
from os.path import join, isdir, splitext, basename, dirname

import json
import re
import sys

KeyBinding = namedtuple('KeyBinding', ('keys', 'command', 'args'))

class PluginSupport:

	USER_PLUGIN_NAME = 'User'

	def __init__(self, shipped_plugins_dir, installed_plugins_dir):
		self.shipped_plugins_dir = shipped_plugins_dir
		self.installed_plugins_dir = installed_plugins_dir
		self._plugins = self._key_bindings_json = None
		self._command_instances = {}
	def initialize(self):
		self._plugins = self._load_plugins()
		self._key_bindings_json = self.load_json('Key Bindings.json') or []
	def on_pane_added(self, pane):
		self._command_instances[pane] = {}
		for plugin in self._plugins:
			for command_name, command_class in plugin.commands.items():
				command = command_class(pane)
				self._command_instances[pane][command_name] = command
	def get_key_bindings_for_pane(self, pane):
		result = []
		commands = self._command_instances[pane]
		for key_binding in self._key_bindings_json:
			keys = key_binding['keys']
			command = commands[key_binding['command']]
			args = key_binding.get('args', {})
			result.append(KeyBinding(keys, command, args))
		return result
	def _load_plugins(self):
		result = []
		for plugin_dir in self._find_plugins():
			plugin = Plugin(plugin_dir)
			plugin.load()
			result.append(plugin)
		return result
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
	def load_json(self, name):
		return load_json(*self._get_json_paths(name))
	def write_json(self, value, name):
		return write_differential_json(value, *self._get_json_paths(name))
	def _get_json_paths(self, name):
		plugin_dirs = [plugin.path for plugin in self._plugins]
		base, ext = splitext(name)
		platform_specific_name = '%s (%s)%s' % (base, platform(), ext)
		result = []
		for plugin_dir in plugin_dirs:
			result.append(join(plugin_dir, name))
			result.append(join(plugin_dir, platform_specific_name))
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
			module = SourceFileLoader(module_name, py_file).load_module()
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
	def __str__(self):
		return '<Plugin %r>' % basename(self.path)

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