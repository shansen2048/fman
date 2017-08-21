from fman import DirectoryPaneCommand, DirectoryPaneListener, ApplicationCommand
from fman.util import listdir_absolute
from glob import glob
from importlib.machinery import SourceFileLoader
from inspect import getmro
from json import JSONDecodeError
from os.path import join, isdir, basename, isfile
from threading import Thread

import inspect
import json
import re
import sys

class Plugin:
	def __init__(self, error_handler, command_callback, key_bindings):
		self._error_handler = error_handler
		self._command_callback = command_callback
		self._key_bindings = key_bindings
		self._application_command_instances = {}
		self._directory_pane_commands = {}
		self._directory_pane_listeners = []
	@property
	def name(self):
		raise NotImplementedError()
	def on_pane_added(self, pane):
		for cmd_name, cmd_class in self._directory_pane_commands.items():
			command = self._instantiate_command(cmd_name, cmd_class, pane)
			pane._register_command(cmd_name, command)
		for listener_class in self._directory_pane_listeners:
			listener = listener_class(pane)
			pane._add_listener(ListenerWrapper(listener, self._error_handler))
	def get_application_commands(self):
		return self._application_command_instances
	def get_directory_pane_commands(self):
		return self._directory_pane_commands
	def run_application_command(self, name, args=None):
		if args is None:
			args = {}
		return self._application_command_instances[name](**args)
	def _register_application_command(self, cls, *args):
		name = _get_command_name(cls)
		self._key_bindings.register_command(name)
		instance = self._instantiate_command(name, cls, *args)
		self._application_command_instances[name] = instance
	def _register_directory_pane_command(self, cls):
		name = _get_command_name(cls)
		self._key_bindings.register_command(name)
		self._directory_pane_commands[name] = cls
	def _register_directory_pane_listener(self, cls):
		self._directory_pane_listeners.append(cls)
	def _instantiate_command(self, cmd_name, cmd_class, *args, **kwargs):
		try:
			command = cmd_class(*args, **kwargs)
		except:
			self._error_handler.report(
				'Could not instantiate command %r.' % cmd_name
			)
			command = lambda *_, **__: None
		return CommandWrapper(
			command, self._error_handler, self._command_callback
		)
	def __str__(self):
		return '<%s %r>' % (self.__class__.__name__, self.name)

def _get_command_name(command_class):
	try:
		command_class = command_class.__name__
	except AttributeError:
		assert isinstance(command_class, str)
	return re.sub(r'([a-z])([A-Z])', r'\1_\2', command_class).lower()

class ExternalPlugin(Plugin):
	def __init__(
		self, error_handler, command_callback, key_bindings, path, config,
		theme, font_database
	):
		super().__init__(error_handler, command_callback, key_bindings)
		self._path = path
		self._config = config
		self._theme = theme
		self._font_database = font_database
	@property
	def name(self):
		return basename(self._path)
	def load(self):
		try:
			self._load()
		except:
			message = 'Plugin %r failed to load.' % self.name
			self._error_handler.report(message)
			return False
		return True
	def _load(self):
		self._config.add_dir(self._path)
		for font in glob(join(self._path, '*.ttf')):
			self._font_database.load(font)
		for css_file in self._config.locate('Theme.css', self._path):
			try:
				self._theme.load(css_file)
			except FileNotFoundError:
				pass
		sys.path.append(self._path)
		self._register_api_classes()
		self._load_key_bindings()
	def _register_api_classes(self):
		for cls in self._load_classes():
			superclasses = getmro(cls)[1:]
			if ApplicationCommand in superclasses:
				self._register_application_command(cls)
			elif DirectoryPaneCommand in superclasses:
				self._register_directory_pane_command(cls)
			elif DirectoryPaneListener in superclasses:
				self._register_directory_pane_listener(cls)
	def _load_key_bindings(self):
		for json_file in self._config.locate('Key Bindings.json', self._path):
			try:
				with open(json_file, 'r') as f:
					bindings = json.load(f)
			except FileNotFoundError:
				pass
			except JSONDecodeError as e:
				self._error_handler.report(
					'Could not load key bindings: ' + e.args[0], exc=False
				)
			except:
				self._error_handler.report('Could not load key bindings.')
			else:
				errors = self._key_bindings.load(bindings)
				for error in errors:
					self._error_handler.report(error)
	def _load_classes(self):
		for package in self._load_packages():
			for cls in [getattr(package, name) for name in dir(package)]:
				if inspect.isclass(cls):
					yield cls
	def _load_packages(self):
		for dir_ in [d for d in listdir_absolute(self._path) if isdir(d)]:
			init = join(dir_, '__init__.py')
			if isfile(init):
				package_name = basename(dir_)
				loader = SourceFileLoader(package_name, init)
				yield loader.load_module()

def get_command_class_name(command_name):
	return ''.join(part.title() for part in command_name.split('_'))

class CommandWrapper:
	def __init__(self, command, error_handler, callback):
		self.command = command
		self.error_handler = error_handler
		self.callback = callback
	def __call__(self, *args, **kwargs):
		Thread(
			target=self._run_in_thread, args=args, kwargs=kwargs, daemon=True
		).start()
	def _run_in_thread(self, *args, **kwargs):
		self.callback.before_command(self.name)
		try:
			self.command(*args, **kwargs)
		except SystemExit as e:
			self.error_handler.handle_system_exit(e.code)
		except:
			message = 'Command %r raised exception.' % self.name
			self.error_handler.report(message)
		else:
			self.callback.after_command(self.name)
	@property
	def name(self):
		return self.command.__class__.__name__
	def get_aliases(self):
		try:
			return self.command.aliases
		except AttributeError:
			class_name = self.command.__class__.__name__
			return re.sub(r'([a-z])([A-Z])', r'\1 \2', class_name)\
					   .lower().capitalize(),

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
	def _notify_listener(self, *args):
		Thread(
			target=self._notify_listener_in_thread, args=args, daemon=True
		).start()
	def _notify_listener_in_thread(self, event, *args):
		listener_method = getattr(self.listener, event)
		try:
			listener_method(*args)
		except:
			self.error_handler.report(
				'DirectoryPaneListener %r raised error.' %
				self.listener.__class__.__name__
			)