from fman import DirectoryPaneCommand, DirectoryPaneListener
from fman.util import listdir_absolute, is_in_subdir
from importlib.machinery import SourceFileLoader
from inspect import getmro
from io import StringIO
from os.path import join, isdir, basename, dirname, isfile
from traceback import extract_tb, print_exception

import re
import sys

USER_PLUGIN_NAME = 'User'

def find_plugin_dirs(shipped_plugins_dir, installed_plugins_dir):
	shipped_plugins = _list_plugins(shipped_plugins_dir)
	installed_plugins = [
		plugin for plugin in _list_plugins(installed_plugins_dir)
		if basename(plugin) != USER_PLUGIN_NAME
	]
	result = shipped_plugins + installed_plugins
	user_plugin = join(installed_plugins_dir, USER_PLUGIN_NAME)
	if isdir(user_plugin):
		result.append(user_plugin)
	return result

def _list_plugins(dir_path):
	try:
		return list(filter(isdir, listdir_absolute(dir_path)))
	except FileNotFoundError:
		return []

class PluginSupport:
	def __init__(self, plugin_dirs, json_io, error_handler):
		self._plugin_dirs = plugin_dirs
		self._json_io = json_io
		self._error_handler = error_handler
		self._plugins = None
		self._key_bindings = None
	def initialize(self):
		self._plugins = self._load_plugins()
		self._key_bindings = self._load_key_bindings()
	def load_json(self, name, default=None, save_on_quit=False):
		return self._json_io.load(name, default, save_on_quit)
	def save_json(self, name, value=None):
		self._json_io.save(name, value)
	def get_sanitized_key_bindings(self):
		return self._key_bindings
	def on_pane_added(self, pane):
		for plugin in self._plugins:
			plugin.on_pane_added(pane)
	def _load_plugins(self):
		result = []
		for plugin_dir in self._plugin_dirs:
			try:
				plugin = Plugin.load(plugin_dir, self._error_handler)
			except:
				message = 'Plugin %r failed to load.' % basename(plugin_dir)
				self._error_handler.report(message)
			else:
				result.append(plugin)
		return result
	def _load_key_bindings(self):
		try:
			bindings = self.load_json('Key Bindings.json', [])
		except:
			self._error_handler.report('Error: Could not load key bindings.')
			return []
		else:
			available_commands = set(self._get_available_commands())
			result, errors = sanitize_key_bindings(bindings, available_commands)
			for error in errors:
				self._error_handler.report(error)
			return result
	def _get_available_commands(self):
		for plugin in self._plugins:
			for command_name in plugin.get_command_names():
				yield command_name

def sanitize_key_bindings(bindings, available_commands):
	if not isinstance(bindings, list):
		error = 'Error: Key bindings should be a list ([...]), not %s.' % \
				type(bindings).__name__
		return [], [error]
	result, errors = [], []
	for binding in bindings:
		try:
			command = binding['command']
		except KeyError:
			errors.append('Error: Each key binding must specify a "command".')
		else:
			if not isinstance(command, str):
				errors.append(
					'Error: A key binding\'s "command" must be a '
					'string, not %s.' % type(command).__name__
				)
			else:
				if command not in available_commands:
					errors.append(
						'Error in key bindings: Command %r does not exist.'
						% command
					)
				else:
					result.append(binding)
	return result, errors

class Plugin:
	@classmethod
	def load(cls, plugin_dir, error_handler):
		command_classes = {}
		listener_classes = []
		for module in cls._load_modules(plugin_dir):
			members = [getattr(module, name) for name in dir(module)]
			for member in members:
				try:
					mro = getmro(member)
				except Exception as not_a_class:
					continue
				def member_is_strict_subclass_of(superclass):
					return superclass in mro[1:]
				if member_is_strict_subclass_of(DirectoryPaneCommand):
					name = _get_command_name(member.__name__)
					command_classes[name] = member
				if member_is_strict_subclass_of(DirectoryPaneListener):
					listener_classes.append(member)
		return cls(plugin_dir, error_handler, command_classes, listener_classes)
	@classmethod
	def _load_modules(cls, plugin_dir):
		result = []
		sys.path.append(plugin_dir)
		for dir_ in [f for f in listdir_absolute(plugin_dir) if isdir(f)]:
			init = join(dir_, '__init__.py')
			if isfile(init):
				package_name = basename(dir_)
				package = SourceFileLoader(package_name, init).load_module()
				result.append(package)
		return result
	def __init__(self, path, error_handler, command_classes, listener_classes):
		self._path = path
		self._error_handler = error_handler
		self._command_classes = command_classes
		self._listener_classes = listener_classes
	def get_command_names(self):
		return list(self._command_classes)
	def on_pane_added(self, pane):
		for command_name, command_class in self._command_classes.items():
			try:
				command = command_class(pane)
			except:
				self._error_handler.report(
					'Could not instantiate command %r.' % command_name
				)
			else:
				command_wrapped = CommandWrapper(command, self._error_handler)
				pane._register_command(command_name, command_wrapped)
		for listener_class in self._listener_classes:
			listener = listener_class(pane)
			pane._add_listener(ListenerWrapper(listener, self._error_handler))
	def __str__(self):
		return '<Plugin %r>' % basename(self._path)

def _get_command_name(command_class_name):
	return re.sub(r'([a-z])([A-Z])', r'\1_\2', command_class_name).lower()

def get_command_class_name(command_name):
	return ''.join(part.title() for part in command_name.split('_'))

class CommandWrapper:
	def __init__(self, command, error_handler):
		self.command = command
		self.error_handler = error_handler
	def __call__(self, *args, **kwargs):
		try:
			return self.command(*args, **kwargs)
		except SystemExit as e:
			self.error_handler.handle_system_exit(e.code)
		except:
			message = 'Command %r raised exception.' % self.name
			self.error_handler.report(message)
	@property
	def name(self):
		return self.command.__class__.__name__

class ListenerWrapper:
	def __init__(self, listener, error_handler):
		self.listener = listener
		self.error_handler = error_handler
	def on_doubleclicked(self, *args):
		self._notify_listener('on_doubleclicked', *args)
	def on_name_edited(self, *args):
		self._notify_listener('on_name_edited', *args)
	def on_path_changed(self):
		self._notify_listener('on_path_changed')
	def on_files_dropped(self, *args):
		self._notify_listener('on_files_dropped', *args)
	def _notify_listener(self, event, *args):
		listener_method = getattr(self.listener, event)
		try:
			listener_method(*args)
		except:
			self.error_handler.report(
				'DirectoryPaneListener %r raised error.' %
				self.listener.__class__.__name__
			)

class PluginErrorHandler:
	def __init__(self, plugin_dirs, app, main_window):
		self.plugin_dirs = plugin_dirs
		self.app = app
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
	def handle_system_exit(self, code=0):
		self.app.exit(code)
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
			if is_in_subdir(dirname(tb_file), plugin_dir):
				return plugin_dir