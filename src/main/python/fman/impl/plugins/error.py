from fman.util import is_in_subdir
from io import StringIO
from os.path import dirname
from traceback import extract_tb, print_exception

import sys

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