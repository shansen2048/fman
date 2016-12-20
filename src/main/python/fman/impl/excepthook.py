from fman.util import get_user

import rollbar
import sys
import threading

class Excepthook:
	def __init__(self, rollbar_token, environment, build_version):
		self.rollbar_token = rollbar_token
		self.environment = environment
		self.build_version = build_version
		self.user_id = None
	def install(self):
		rollbar.init(
			self.rollbar_token, self.environment,
			code_version=self.build_version
		)
		sys.excepthook = self
		self._enable_excepthook_for_threads()
	def __call__(self, type, value, traceback):
		sys.__excepthook__(type, value, traceback)
		request = RollbarRequest(self.user_id) if self.user_id else None
		rollbar.report_exc_info((type, value, traceback), request)
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

class RollbarRequest:
	def __init__(self, user_id):
		self.user_id = user_id
	@property
	def rollbar_person(self):
		return {
			'id': self.user_id, 'username': get_user()
		}