from contextlib import contextmanager
from fman.impl.plugins.plugin import ReportExceptions
from threading import Thread
from weakref import WeakKeyDictionary

import re

_DEFAULT = object()

class CommandRegistry:
	def __init__(self, error_handler, callback):
		self._error_handler = error_handler
		self._callback = callback
		self._command_classes = {}
		self._command_instances = WeakKeyDictionary()
	def register_command(self, name, cls):
		self._command_classes[name] = cls
	def unregister_command(self, name):
		del self._command_classes[name]
	def get_commands(self):
		return set(self._command_classes)
	def execute_command(self, name, args, pane, file_under_cursor=_DEFAULT):
		command = self._get_command(pane, name)
		if command is None:
			# Command could not be instantiated.
			return
		thread_args = (name, command, args, pane, file_under_cursor)
		Thread(
			target=self._execute_command_async, args=thread_args, daemon=True
		).start()
	def get_command_aliases(self, name):
		command_class = self._command_classes[name]
		try:
			return command_class.aliases
		except AttributeError:
			return re.sub(r'([a-z])([A-Z])', r'\1 \2', command_class.__name__) \
				.lower().capitalize(),
	def is_command_visible(self, name, pane, file_under_cursor=_DEFAULT):
		command = self._get_command(pane, name)
		if command is None:
			# Command could not be instantiated.
			return None
		with self._set_context(pane, file_under_cursor):
			return command.is_visible()
	def _execute_command_async(
		self, name, command, args, pane, file_under_cursor
	):
		self._callback.before_command(name)
		with self._set_context(pane, file_under_cursor):
			try:
				msg_on_err = \
					'Command %r raised error.' % command.__class__.__name__
				with ReportExceptions(self._error_handler, msg_on_err):
					command(**args)
			except Exception:
				pass
			else:
				self._callback.after_command(name)
	def _get_command(self, pane, name):
		try:
			commands = self._command_instances[pane]
		except KeyError:
			commands = self._command_instances[pane] = {}
		try:
			return commands[name]
		except KeyError:
			cmd_class = self._command_classes[name]
			try:
				result = cmd_class(pane)
			except Exception:
				self._error_handler.report(
					'Could not instantiate command %r.' % cmd_class.__name__
				)
				result = None
			commands[name] = result
			return result
	@contextmanager
	def _set_context(self, pane, file_under_cursor=_DEFAULT):
		if file_under_cursor is not _DEFAULT:
			cm = pane._override_file_under_cursor(file_under_cursor)
			cm.__enter__()
		yield
		if file_under_cursor is not _DEFAULT:
			cm.__exit__(None, None, None)