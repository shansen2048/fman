from fman import DirectoryPaneCommand, DirectoryPaneListener, ApplicationCommand
from fman.util import listdir_absolute
from importlib.machinery import SourceFileLoader
from inspect import getmro
from os.path import join, isdir, basename, isfile
from threading import Thread

import re
import sys

class Plugin:
	def __init__(self, path, error_handler):
		self._path = path
		self._error_handler = error_handler
		self._application_command_instances = {}
		self._directory_pane_commands = {}
		self._directory_pane_listeners = []
	def load(self):
		for cls, superclasses in self._load_classes():
			if ApplicationCommand in superclasses:
				name = _get_command_name(cls)
				instance = self._instantiate_command(name, cls)
				self._application_command_instances[name] = instance
			elif DirectoryPaneCommand in superclasses:
				self._directory_pane_commands[_get_command_name(cls)] = cls
			elif DirectoryPaneListener in superclasses:
				self._directory_pane_listeners.append(cls)
	def on_pane_added(self, pane):
		for cmd_name, cmd_class in self._directory_pane_commands.items():
			command = self._instantiate_command(cmd_name, cmd_class, pane)
			pane._register_command(cmd_name, command)
		for listener_class in self._directory_pane_listeners:
			listener = listener_class(pane)
			pane._add_listener(ListenerWrapper(listener, self._error_handler))
	def get_application_commands(self):
		return set(self._application_command_instances)
	def get_directory_pane_commands(self):
		return set(self._directory_pane_commands)
	def run_application_command(self, name, args=None):
		if args is None:
			args = {}
		return self._application_command_instances[name](**args)
	def _load_classes(self):
		for package in self._load_packages():
			for member in [getattr(package, name) for name in dir(package)]:
				try:
					mro = getmro(member)
				except Exception as not_a_class:
					continue
				yield member, mro[1:]
	def _load_packages(self):
		sys.path.append(self._path)
		for dir_ in [d for d in listdir_absolute(self._path) if isdir(d)]:
			init = join(dir_, '__init__.py')
			if isfile(init):
				package_name = basename(dir_)
				yield SourceFileLoader(package_name, init).load_module()
	def _instantiate_command(self, cmd_name, cmd_class, *args, **kwargs):
		try:
			command = cmd_class(*args, **kwargs)
		except:
			self._error_handler.report(
				'Could not instantiate command %r.' % cmd_name
			)
			command = lambda *_, **__: None
		return CommandWrapper(command, self._error_handler)
	def __str__(self):
		return '<Plugin %r>' % basename(self._path)

def _get_command_name(command_class):
	try:
		command_class = command_class.__name__
	except AttributeError:
		assert isinstance(command_class, str)
	return re.sub(r'([a-z])([A-Z])', r'\1_\2', command_class).lower()

def get_command_class_name(command_name):
	return ''.join(part.title() for part in command_name.split('_'))

class CommandWrapper:
	def __init__(self, command, error_handler):
		self.command = command
		self.error_handler = error_handler
	def __call__(self, *args, **kwargs):
		Thread(
			target=self._run_in_thread, args=args, kwargs=kwargs, daemon=True
		).start()
	def _run_in_thread(self, *args, **kwargs):
		try:
			self.command(*args, **kwargs)
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