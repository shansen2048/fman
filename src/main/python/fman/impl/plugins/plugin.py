from fman import DirectoryPaneCommand, DirectoryPaneListener
from fman.util import listdir_absolute
from importlib.machinery import SourceFileLoader
from inspect import getmro
from os.path import join, isdir, basename, isfile

import re
import sys

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