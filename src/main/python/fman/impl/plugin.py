from collections import namedtuple
from fman import DirectoryPaneCommand, PLATFORM, DirectoryPaneListener
from fman.util import listdir_absolute
from importlib.machinery import SourceFileLoader
from inspect import getmro
from io import StringIO
from os import makedirs
from os.path import join, isdir, splitext, basename, dirname, isfile, relpath, \
	realpath, pardir, exists
from traceback import extract_tb, print_exception

import json
import os
import re
import sys

KeyBinding = namedtuple('KeyBinding', ('keys', 'command', 'args'))

class PluginSupport:

	USER_PLUGIN_NAME = 'User'

	def __init__(self, shipped_plugins_dir, installed_plugins_dir):
		self.shipped_plugins_dir = shipped_plugins_dir
		self.installed_plugins_dir = installed_plugins_dir
		self._cached_jsons = {}
		self._jsons_to_save_on_quit = set()
		self._plugins = self._key_bindings_json = None
		self._command_instances = {}
		self._listener_instances = {}
	def initialize(self):
		self._plugins, errors = self._load_plugins()
		self._key_bindings_json = self.load_json('Key Bindings.json', [])
		errors.extend(
			'Error in key bindings: Command %r does not exist.' % command
			for command in self._remove_missing_commands()
		)
		return errors
	def on_pane_added(self, pane):
		self._command_instances[pane] = {}
		self._listener_instances[pane] = []
		for plugin in self._plugins:
			for command_name, command_class in plugin.command_classes.items():
				command = command_class(pane)
				self._command_instances[pane][command_name] = command
			for listener_class in plugin.listener_classes:
				self._listener_instances[pane].append(listener_class(pane))
		pane.path_changed.connect(self.on_path_changed)
	def on_quit(self):
		for name in self._jsons_to_save_on_quit:
			self.save_json(name)
	def get_key_bindings_for_pane(self, pane):
		result = []
		commands = self._command_instances[pane]
		for key_binding in self._key_bindings_json:
			keys = key_binding['keys']
			command = commands[key_binding['command']]
			args = key_binding.get('args', {})
			result.append(KeyBinding(keys, command, args))
		return result
	def on_doubleclicked(self, pane, file_path):
		for listener in self._listener_instances[pane]:
			listener.on_doubleclicked(file_path)
	def on_name_edited(self, pane, file_path, new_name):
		for listener in self._listener_instances[pane]:
			listener.on_name_edited(file_path, new_name)
	def on_path_changed(self, pane):
		for listener in self._listener_instances[pane]:
			listener.on_path_changed()
	def load_json(self, name, default=None, save_on_quit=False):
		if name not in self._cached_jsons:
			result = load_json(*self._get_json_paths(name))
			if result is None:
				result = default
			self._cached_jsons[name] = result
		if save_on_quit:
			self._jsons_to_save_on_quit.add(name)
		return self._cached_jsons[name]
	def save_json(self, name, value=None):
		if value is None:
			value = self._cached_jsons[name]
		write_differential_json(value, *self._get_json_paths(name))
		self._cached_jsons[name] = value
	@property
	def user_plugin(self):
		return join(self.installed_plugins_dir, self.USER_PLUGIN_NAME)
	def _load_plugins(self):
		result, errors = [], []
		for plugin_dir in self._find_plugin_dirs():
			plugin = Plugin(plugin_dir)
			result.append(plugin)
			if not exists(plugin_dir):
				# This happens the first time fman is started. We still want the
				# User plugin to be in `result` because this list is used to
				# compute the destination path for save_json(...).
				assert plugin_dir == self.user_plugin
				continue
			try:
				plugin.load()
			except Exception as e:
				plugin_name = basename(plugin_dir)
				traceback = self.get_plugin_traceback(e)
				errors.append(
					'Plugin %r failed to load.\n\n%s' % (plugin_name, traceback)
				)
		return result, errors
	def _find_plugin_dirs(self):
		shipped_plugins = self._list_plugins(self.shipped_plugins_dir)
		installed_plugins = [
			plugin for plugin in self._list_plugins(self.installed_plugins_dir)
		 	if basename(plugin) != self.USER_PLUGIN_NAME
		]
		return shipped_plugins + installed_plugins + [self.user_plugin]
	def _list_plugins(self, dir_path):
		try:
			return list(filter(isdir, listdir_absolute(dir_path)))
		except FileNotFoundError:
			return []
	def _get_json_paths(self, name):
		plugin_dirs = [plugin.path for plugin in self._plugins]
		base, ext = splitext(name)
		platform_specific_name = '%s (%s)%s' % (base, PLATFORM, ext)
		result = []
		for plugin_dir in plugin_dirs:
			result.append(join(plugin_dir, name))
			result.append(join(plugin_dir, platform_specific_name))
		return result
	def get_plugin_traceback(self, exc):
		tb = exc.__traceback__
		def is_in_plugin(tb):
			tb_file = extract_tb(tb)[0][0]
			for plugin_dir in self._find_plugin_dirs():
				if self._is_in_subdir(dirname(tb_file), plugin_dir):
					return True
			return False
		while tb and not is_in_plugin(tb):
			tb = tb.tb_next
		result = StringIO()
		print_exception(exc.__class__, exc.with_traceback(tb), tb, file=result)
		return result.getvalue()
	def _is_in_subdir(self, file_path, directory):
		rel = relpath(realpath(dirname(file_path)), realpath(directory))
		return not (rel == pardir or rel.startswith(pardir + os.sep))
	def _remove_missing_commands(self):
		result = []
		available_commands = set(
			command_name
			for plugin in self._plugins
			for command_name in plugin.command_classes
		)
		for key_binding in self._key_bindings_json[:]:
			command = key_binding['command']
			if command not in available_commands:
				self._key_bindings_json.remove(key_binding)
				result.append(command)
		return result

class Plugin:
	def __init__(self, dir_path):
		self.path = dir_path
		self.command_classes = {}
		self.listener_classes = []
	def load(self):
		for module in self._load_modules():
			members = [getattr(module, name) for name in dir(module)]
			for cls in members:
				try:
					mro = getmro(cls)
				except Exception as not_a_class:
					continue
				if DirectoryPaneCommand in mro:
					name = self._get_command_name(cls.__name__)
					self.command_classes[name] = cls
				if DirectoryPaneListener in mro:
					self.listener_classes.append(cls)
	def _load_modules(self):
		result = []
		sys.path.append(self.path)
		for dir_ in [f for f in listdir_absolute(self.path) if isdir(f)]:
			init = join(dir_, '__init__.py')
			if isfile(init):
				package_name = basename(dir_)
				package = SourceFileLoader(package_name, init).load_module()
				result.append(package)
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
	if obj == old_obj:
		return
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