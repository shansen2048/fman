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

USER_PLUGIN_NAME = 'User'

class PluginSupport:
	def __init__(self, plugin_dirs, error_handler):
		self.plugin_dirs = plugin_dirs
		self.error_handler = error_handler
		self._cached_jsons = {}
		self._jsons_to_save_on_quit = set()
		self._plugins = None
		self._key_bindings_json = []
		self._command_instances = {}
		self._listener_instances = {}
	def initialize(self):
		self._plugins = self._load_plugins()
		self._key_bindings_json = self._load_key_bindings()
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
			try:
				self.save_json(name)
			except ValueError as error_computing_delta:
				# This can happen for a variety of reasons. One example: When
				# multiple instances of fman are open and another instance has
				# already written to the same json file, then the delta
				# computation may fail with a ValueError. Ignore this so we can
				# at least save the other files in _jsons_to_save_on_quit:
				pass
	def get_key_bindings_for_pane(self, pane):
		result = []
		commands = self._command_instances[pane]
		for key_binding in self._key_bindings_json:
			keys = key_binding['keys']
			command_name = key_binding['command']
			command = CommandWrapper(commands[command_name], self.error_handler)
			args = key_binding.get('args', {})
			result.append(KeyBinding(keys, command, args))
		return result
	def on_doubleclicked(self, pane, file_path):
		for listener in self._listener_instances[pane]:
			try:
				listener.on_doubleclicked(file_path)
			except:
				self._report_listener_error(listener)
	def on_name_edited(self, pane, file_path, new_name):
		for listener in self._listener_instances[pane]:
			try:
				listener.on_name_edited(file_path, new_name)
			except:
				self._report_listener_error(listener)
	def on_path_changed(self, pane):
		for listener in self._listener_instances[pane]:
			try:
				listener.on_path_changed()
			except:
				self._report_listener_error(listener)
	def _report_listener_error(self, listener):
		self.error_handler.report(
			'DirectoryPaneListener %r raised error.' %
			listener.__class__.__name__
		)
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
	def _load_plugins(self):
		result = []
		for plugin_dir in self.plugin_dirs:
			plugin = Plugin(plugin_dir)
			result.append(plugin)
			if not exists(plugin_dir):
				# This happens the first time fman is started. We still want the
				# User plugin to be in `result` because this list is used to
				# compute the destination path for save_json(...).
				assert basename(plugin_dir) == USER_PLUGIN_NAME
				continue
			try:
				plugin.load()
			except:
				message = 'Plugin %r failed to load.' % basename(plugin_dir)
				self.error_handler.report(message)
		return result
	def _get_json_paths(self, name):
		plugin_dirs = [plugin.path for plugin in self._plugins]
		base, ext = splitext(name)
		platform_specific_name = '%s (%s)%s' % (base, PLATFORM, ext)
		result = []
		for plugin_dir in plugin_dirs:
			result.append(join(plugin_dir, name))
			result.append(join(plugin_dir, platform_specific_name))
		return result
	def _load_key_bindings(self):
		result = []
		report = self.error_handler.report
		try:
			bindings = self.load_json('Key Bindings.json', [])
		except:
			report('Error: Could not load key bindings.')
		else:
			if not isinstance(bindings, list):
				report(
					'Error: Key bindings should be a list ([...]), not %s.' %
					type(self._key_bindings_json).__name__
				)
			else:
				available_commands = set(
					command_name
					for plugin in self._plugins
					for command_name in plugin.command_classes
				)
				for binding in bindings:
					try:
						command = binding['command']
					except KeyError:
						report(
							'Error: Each key binding must specify a "command".'
						)
					else:
						if not isinstance(command, str):
							report(
								'Error: A key binding\'s "command" must be a '
								'string, not %s.' % type(command).__name__
							)
						else:
							if command not in available_commands:
								report(
									'Error in key bindings: Command %r does '
									'not exist.' % command
								)
							else:
								result.append(binding)
		return result

def find_plugin_dirs(shipped_plugins_dir, installed_plugins_dir):
	shipped_plugins = _list_plugins(shipped_plugins_dir)
	installed_plugins = [
		plugin for plugin in _list_plugins(installed_plugins_dir)
		if basename(plugin) != USER_PLUGIN_NAME
	]
	user_plugin = join(installed_plugins_dir, USER_PLUGIN_NAME)
	return shipped_plugins + installed_plugins + [user_plugin]

def _list_plugins(dir_path):
	try:
		return list(filter(isdir, listdir_absolute(dir_path)))
	except FileNotFoundError:
		return []

class PluginErrorHandler:
	def __init__(self, plugin_dirs, main_window):
		self.plugin_dirs = plugin_dirs
		self.main_window = main_window
		self.main_window_initialized = False
		self.pending_error_messages = []
	def report(self, message):
		exc = sys.exc_info()[1]
		if exc:
			message += '\n\n' + self._get_plugin_traceback(exc)
		if self.main_window_initialized:
			self.main_window.show_alert(message)
		else:
			self.pending_error_messages.append(message)
	def on_main_window_shown(self):
		if self.pending_error_messages:
			self.main_window.show_alert(self.pending_error_messages[0])
		self.main_window_initialized = True
	def _get_plugin_traceback(self, exc):
		tb = exc.__traceback__
		while tb:
			plugin_dir = self._get_plugin_dir(tb)
			if plugin_dir:
				break
			tb = tb.tb_next
		traceback_ = StringIO()
		print_exception(
			exc.__class__, exc.with_traceback(tb), tb, file=traceback_
		)
		return traceback_.getvalue()
	def _get_plugin_dir(self, traceback_):
		tb_file = extract_tb(traceback_)[0][0]
		for plugin_dir in self.plugin_dirs:
			if self._is_in_subdir(dirname(tb_file), plugin_dir):
				return plugin_dir
	def _is_in_subdir(self, file_path, directory):
		rel = relpath(realpath(dirname(file_path)), realpath(directory))
		return not (rel == pardir or rel.startswith(pardir + os.sep))

class CommandWrapper:
	def __init__(self, command, error_handler):
		self.wrapped_command = command
		self.error_handler = error_handler
	def __call__(self, *args, **kwargs):
		try:
			return self.wrapped_command(*args, **kwargs)
		except:
			command_name = self.wrapped_command.__class__.__name__
			message = 'Command %r raised exception.' % command_name
			self.error_handler.report(message)

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
				is_strict_subclass_of = lambda superclass: superclass in mro[1:]
				if is_strict_subclass_of(DirectoryPaneCommand):
					name = self._get_command_name(cls.__name__)
					self.command_classes[name] = cls
				if is_strict_subclass_of(DirectoryPaneListener):
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