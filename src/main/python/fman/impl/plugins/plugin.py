from fman import DirectoryPaneCommand, DirectoryPaneListener, ApplicationCommand
from fman.fs import FileSystem, Column
from fman.impl.util import listdir_absolute
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
	def __init__(
		self, error_handler, command_callback, key_bindings, mother_fs, window
	):
		self._error_handler = error_handler
		self._command_callback = command_callback
		self._key_bindings = key_bindings
		self._mother_fs = mother_fs
		self._window = window
		self._application_command_instances = {}
		self._directory_pane_commands = {}
		self._directory_pane_listeners = []
	@property
	def name(self):
		raise NotImplementedError()
	def on_pane_added(self, pane):
		for cmd_name, cmd_class in self._directory_pane_commands.items():
			command = self._instantiate_command(
				cmd_class, (pane,), DirectoryPaneCommandWrapper
			)
			pane._register_command(cmd_name, command)
		for listener_class in self._directory_pane_listeners:
			pane._add_listener(
				self._instantiate_listener(listener_class, pane)
			)
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
		instance = self._instantiate_command(cls, [self._window] + list(args))
		self._application_command_instances[name] = instance
	def _unregister_application_command(self, cls):
		name = _get_command_name(cls)
		del self._application_command_instances[name]
		self._key_bindings.unregister_command(name)
	def _register_directory_pane_command(self, cls):
		name = _get_command_name(cls)
		self._key_bindings.register_command(name)
		self._directory_pane_commands[name] = cls
	def _unregister_directory_pane_command(self, cls):
		name = _get_command_name(cls)
		del self._directory_pane_commands[name]
		self._key_bindings.unregister_command(name)
	def _register_directory_pane_listener(self, cls):
		self._directory_pane_listeners.append(cls)
	def _unregister_directory_pane_listener(self, cls):
		self._directory_pane_listeners.remove(cls)
	def _register_file_system(self, cls):
		instance = self._instantiate_file_system(cls)
		if instance:
			self._mother_fs.add_child(cls.scheme, instance)
	def _unregister_file_system(self, cls):
		self._mother_fs.remove_child(cls.scheme)
	def _register_column(self, cls):
		instance = self._instantiate_column(cls)
		if instance:
			self._mother_fs.register_column(cls.get_qualified_name(), instance)
	def _unregister_column(self, cls):
		self._mother_fs.unregister_column(cls.get_qualified_name())
	def _instantiate_command(self, cmd_class, args, wrapper_cls=None):
		if wrapper_cls is None:
			wrapper_cls = CommandWrapper
		try:
			command = cmd_class(*args)
		except Exception:
			self._error_handler.report(
				'Could not instantiate command %r.' % cmd_class.__name__
			)
			command = lambda *_, **__: None
		return wrapper_cls(
			command, self._error_handler, self._command_callback
		)
	def _instantiate_listener(self, listener_class, *args, **kwargs):
		try:
			listener = listener_class(*args, **kwargs)
		except Exception:
			self._error_handler.report(
				'Could not instantiate listener %r.' % listener_class.__name__
			)
			listener = DirectoryPaneListener(*args, **kwargs)
		return ListenerWrapper(listener, self._error_handler)
	def _instantiate_file_system(self, fs_cls):
		try:
			instance = fs_cls()
		except Exception:
			self._error_handler.report(
				'Could not instantiate file system %r.' % fs_cls.__name__
			)
		else:
			return FileSystemWrapper(
				instance, self._mother_fs, self._error_handler
			)
	def _instantiate_column(self, col_cls):
		try:
			instance = col_cls()
		except Exception:
			self._error_handler.report(
				'Could not instantiate Column %r.' % col_cls.__name__
			)
		else:
			return ColumnWrapper(instance, self._error_handler)
	def __str__(self):
		return '<%s %r>' % (self.__class__.__name__, self.name)

def _get_command_name(command_class):
	try:
		command_class = command_class.__name__
	except AttributeError:
		assert isinstance(command_class, str)
	return re.sub(r'([a-z])([A-Z])', r'\1_\2', command_class).lower()

class ExternalPlugin(Plugin):
	def __init__(self, path, config, theme, font_database, *super_args):
		super().__init__(*super_args)
		self._path = path
		self._config = config
		self._theme = theme
		self._font_database = font_database
		self._unload_actions = []
	@property
	def name(self):
		return basename(self._path)
	def load(self):
		try:
			self._load()
		except Exception:
			self._error_handler.report('Plugin %r failed to load.' % self.name)
			return False
		return True
	def _load(self):
		self._register_plugin_dir()
		self._load_config()
		for font in glob(join(self._path, '*.ttf')):
			self._load_font(font)
		for css_file in self._config.locate('Theme.css', self._path):
			try:
				self._load_css_file(css_file)
			except FileNotFoundError:
				pass
		self._extend_sys_path()
		self._load_classes()
		self._load_key_bindings()
	def _register_plugin_dir(self):
		self._error_handler.add_dir(self._path)
		self._add_unload_action(self._error_handler.remove_dir, self._path)
	def _load_config(self):
		self._config.add_dir(self._path)
		self._add_unload_action(self._config.remove_dir, self._path)
	def _load_font(self, font):
		self._font_database.load(font)
		self._add_unload_action(self._font_database.unload, font)
	def _load_css_file(self, css_file):
		self._theme.load(css_file)
		self._add_unload_action(self._theme.unload, css_file)
	def _extend_sys_path(self):
		sys.path.append(self._path)
		self._add_unload_action(sys.path.remove, self._path)
	def _load_classes(self):
		for package in self._load_packages():
			for cls in self._iterate_classes(package):
				superclasses = getmro(cls)[1:]
				if ApplicationCommand in superclasses:
					register = self._register_application_command
					unregister = self._unregister_application_command
				elif DirectoryPaneCommand in superclasses:
					register = self._register_directory_pane_command
					unregister = self._unregister_directory_pane_command
				elif DirectoryPaneListener in superclasses:
					register = self._register_directory_pane_listener
					unregister = self._unregister_directory_pane_listener
				elif FileSystem in superclasses:
					register = self._register_file_system
					unregister = self._unregister_file_system
				elif Column in superclasses:
					register = self._register_column
					unregister = self._unregister_column
				else:
					continue
				register(cls)
				self._add_unload_action(unregister, cls)
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
			except Exception:
				self._error_handler.report('Could not load key bindings.')
			else:
				errors = self._key_bindings.load(bindings)
				self._add_unload_action(self._key_bindings.unload, bindings)
				for error in errors:
					self._error_handler.report(error)
	def _add_unload_action(self, f, *args, **kwargs):
		self._unload_actions.append((f, args, kwargs))
	def unload(self):
		for f, args, kwargs in reversed(self._unload_actions):
			f(*args, **kwargs)
		self._unload_actions = []
	def _load_packages(self):
		for dir_ in [d for d in listdir_absolute(self._path) if isdir(d)]:
			init = join(dir_, '__init__.py')
			if isfile(init):
				package_name = basename(dir_)
				loader = SourceFileLoader(package_name, init)
				yield loader.load_module()
	def _iterate_classes(self, module):
		for cls in [getattr(module, name) for name in dir(module)]:
			if inspect.isclass(cls):
				yield cls

def get_command_class_name(command_name):
	return ''.join(part.title() for part in command_name.split('_'))

class Wrapper:
	def __init__(self, wrapped, type_name, error_handler):
		self._wrapped = wrapped
		self._type_name = type_name
		self._error_handler = error_handler
	def unwrap(self):
		return self._wrapped
	@property
	def _class_name(self):
		return self._wrapped.__class__.__name__
	def _report_exceptions(self, exclude=None):
		message = '%s %r raised error.' % (self._type_name, self._class_name)
		return ReportExceptions(self._error_handler, message, exclude)

class ReportExceptions:
	def __init__(self, error_handler, message, exclude=None):
		if exclude is None:
			exclude = set()
		if not isinstance(exclude, set):
			# Consider ReportExceptions(..., exclude=StopIteration,): At first
			# sight, this looks fine. But it isn't! In this case, exclude is not
			# a tuple, but equal to just StopIteration. The above would have
			# to be written as ..., exclude=(StopIteration,). To avoid falling
			# into this trap, we require `exclude` to be a set:
			raise ValueError('exclude must be a set')
		self.exception = None
		self._exclude = exclude
		self._error_handler = error_handler
		self._message = message
	def __enter__(self):
		return self
	def __exit__(self, exc_type, exc_val, exc_tb):
		if not exc_val:
			return
		self.exception = exc_val
		if isinstance(exc_val, SystemExit):
			exc_code = 0 if exc_val.code is None else exc_val.code
			self._error_handler.handle_system_exit(exc_code)
		elif exc_type not in self._exclude:
			self._error_handler.report(self._message, exc_val)

class CommandWrapper(Wrapper):
	def __init__(self, command, error_handler, callback):
		super().__init__(command, 'Command', error_handler)
		self._callback = callback
	def __call__(self, *args, **kwargs):
		Thread(
			target=self._run_in_thread, args=args, kwargs=kwargs, daemon=True
		).start()
	@property
	def aliases(self):
		return self._wrapped.aliases
	def is_visible(self):
		return self._wrapped.is_visible()
	def _run_in_thread(self, *args, **kwargs):
		self._callback.before_command(self._class_name)
		try:
			with self._report_exceptions():
				self._wrapped(*args, **kwargs)
		except Exception:
			pass
		else:
			self._callback.after_command(self._class_name)

class DirectoryPaneCommandWrapper(CommandWrapper):
	def _run_in_thread(self, file_under_cursor, **kwargs):
		pane = self.unwrap().pane
		with pane._override_file_under_cursor(file_under_cursor):
			super()._run_in_thread(**kwargs)

class ListenerWrapper(Wrapper):
	def __init__(self, listener, error_handler):
		super().__init__(listener, 'DirectoryPaneListener', error_handler)
	def on_doubleclicked(self, *args):
		self._notify_listener('on_doubleclicked', *args)
	def on_name_edited(self, *args):
		self._notify_listener('on_name_edited', *args)
	def on_path_changed(self):
		self._notify_listener('on_path_changed')
	def on_files_dropped(self, *args):
		self._notify_listener('on_files_dropped', *args)
	def on_command(self, command, args):
		try:
			with self._report_exceptions():
				return self._wrapped.on_command(command, args)
		except Exception:
			return None
	def before_location_change(self, *args):
		try:
			with self._report_exceptions():
				return self._wrapped.before_location_change(*args)
		except Exception:
			return None
	def on_location_bar_clicked(self, *args):
		self._notify_listener('on_location_bar_clicked', *args)
	def _notify_listener(self, *args):
		Thread(
			target=self._notify_listener_in_thread, args=args, daemon=True
		).start()
	def _notify_listener_in_thread(self, event, *args):
		listener_method = getattr(self._wrapped, event)
		try:
			with self._report_exceptions():
				listener_method(*args)
		except Exception:
			pass

class FileSystemWrapper(Wrapper):
	def __init__(self, file_system, mother_fs, error_handler):
		super().__init__(file_system, 'FileSystem', error_handler)
		self._mother_fs = mother_fs
	def get_default_columns(self, path):
		result_on_error = 'core.Name',
		try:
			with self._report_exceptions():
				result = self._wrapped.get_default_columns(path)
		except Exception:
			return result_on_error
		available_columns = self._mother_fs.get_registered_column_names()
		for col_name in result:
			if col_name not in available_columns:
				self._error_handler.report(
					"Error: %s.get_default_columns(...) returned a column "
					"that does not exist: %r. Should have been one of: %s." % (
						self._class_name, col_name,
						', '.join(map(repr, available_columns))
					)
				)
				return result_on_error
		return result
	def iterdir(self, path):
		try:
			iterdir = self._wrapped.iterdir
		except AttributeError:
			self._error_handler.report(
				"Error: FileSystem %r does not implement iterdir(...)." %
				self._class_name,
				exc=False
			)
		else:
			try:
				with self._report_exceptions():
					result = iterdir(path)
			except Exception:
				pass
			else:
				try:
					iterable = iter(result)
				except TypeError:
					self._error_handler.report(
						"Error: %s.iterdir(...) returned %r instead of an "
						"iterable such as ['a.txt', 'b.jpg']." %
						(self._class_name, result),
						exc=False
					)
				else:
					showed_error = False
					while True:
						try:
							with self._report_exceptions(
								exclude={StopIteration, FileNotFoundError}
							):
								item = next(iterable)
						except FileNotFoundError:
							# Let caller know that `path` disappeared.
							raise
						except Exception: # Includes StopIteration
							break
						else:
							if isinstance(item, str):
								yield item
							else:
								if not showed_error:
									self._error_handler.report(
										"Error: %s.iterdir(...) yielded %r "
										"instead of a string such as "
										"'file.txt'." % (
											self._class_name, item),
											exc=False
										)
									showed_error = True
	def __getattr__(self, item):
		return getattr(self._wrapped, item)

class ColumnWrapper(Wrapper):
	def __init__(self, wrapped, error_handler):
		super().__init__(wrapped, 'Column', error_handler)
	def get_str(self, url):
		try:
			with self._report_exceptions(exclude={FileNotFoundError}):
				return self._wrapped.get_str(url)
		except Exception:
			return ''
	def get_sort_value(self, url, is_ascending):
		# We always return a tuple (error occurred, sort value) to ensure
		# comparisons can be performed even when errors occur and there is no
		# sort value.
		try:
			with self._report_exceptions(exclude={FileNotFoundError}):
				return False, self._wrapped.get_sort_value(url, is_ascending)
		except Exception:
			return True, 0
	def __getattr__(self, item):
		return getattr(self._wrapped, item)