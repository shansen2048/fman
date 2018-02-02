from collections import namedtuple
from fman.impl.util import is_below_dir
from os.path import basename
from traceback import extract_tb

import rollbar
import sys
import threading

class Excepthook:
	def __init__(self, plugin_dirs, plugin_error_handler):
		self._plugin_dirs = plugin_dirs
		self._plugin_error_handler = plugin_error_handler
	def install(self):
		sys.excepthook = self
		self._enable_excepthook_for_threads()
	def set_user(self, user):
		pass
	def __call__(self, exc_type, exc_value, exc_tb):
		causing_plugin = self._get_plugin_causing_error(exc_tb)
		if causing_plugin and basename(causing_plugin) != 'Core':
			self._plugin_error_handler.report(
				'Plugin %r raised an error.' % basename(causing_plugin)
			)
		else:
			if not isinstance(exc_value, SystemExit):
				self._handle_nonplugin_error(exc_type, exc_value, exc_tb)
	def _handle_nonplugin_error(self, exc_type, exc_value, exc_tb):
		sys.__excepthook__(exc_type, exc_value, exc_tb)
	def _get_plugin_causing_error(self, traceback):
		for frame in extract_tb(traceback):
			for plugin_dir in self._plugin_dirs:
				if is_below_dir(frame.filename, plugin_dir):
					return plugin_dir
	def _enable_excepthook_for_threads(self):
		"""
		`sys.excepthook` isn't called for exceptions raised in non-main-threads.
		This workaround fixes this for instances of (non-subclasses of) Thread.
		See: http://bugs.python.org/issue1230540
		"""
		init_original = threading.Thread.__init__

		def init(self, *args, **kwargs):
			init_original(self, *args, **kwargs)
			run_original = self.run

			def run_with_except_hook(*args2, **kwargs2):
				try:
					run_original(*args2, **kwargs2)
				except Exception:
					sys.excepthook(*sys.exc_info())

			self.run = run_with_except_hook

		threading.Thread.__init__ = init

class RollbarExcepthook(Excepthook):
	def __init__(
		self, rollbar_token, environment, fman_version, plugin_dirs,
		plugin_error_handler
	):
		super().__init__(plugin_dirs, plugin_error_handler)
		self._rollbar_token = rollbar_token
		self._environment = environment
		self._fman_version = fman_version
		self._user = None
	def install(self):
		rollbar.init(
			self._rollbar_token, self._environment,
			code_version=self._fman_version
		)
		super().install()
	def set_user(self, user):
		self._user = user
	def _handle_nonplugin_error(self, exc_type, exc_value, exc_tb):
		super()._handle_nonplugin_error(exc_type, exc_value, exc_tb)
		request = RollbarRequest(self._user) if self._user else None
		rollbar.report_exc_info((exc_type, exc_value, exc_tb), request)

RollbarRequest = namedtuple('RollbarRequest', ('user_id',))