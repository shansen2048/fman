import rollbar
import sys
import threading

class Excepthook:
	def __init__(self, rollbar_token, environment, fman_version):
		self._rollbar_token = rollbar_token
		self._environment = environment
		self._fman_version = fman_version
	def install(self):
		rollbar.init(
			self._rollbar_token, self._environment,
			code_version=self._fman_version
		)
		sys.excepthook = self
		self._enable_excepthook_for_threads()
	def __call__(self, type, value, traceback):
		sys.__excepthook__(type, value, traceback)
		rollbar.report_exc_info((type, value, traceback))
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