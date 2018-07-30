from collections import namedtuple
from fbs_runtime.application_context import cached_property
from fman.impl.util import os_
from time import time

import rollbar
import sys
import threading
import traceback

class Excepthook:
	def __init__(self, plugin_error_handler):
		self._plugin_error_handler = plugin_error_handler
	def install(self):
		sys.excepthook = self
		self._enable_excepthook_for_threads()
	def set_user(self, user):
		pass
	def __call__(self, exc_type, exc_value, exc_tb):
		is_plugin_error = self._plugin_error_handler.handle(exc_tb)
		if not is_plugin_error and not isinstance(exc_value, SystemExit):
			enriched_tb = \
				self._add_missing_frames(exc_tb) if exc_tb else exc_tb
			self._handle_nonplugin_error(exc_type, exc_value, enriched_tb)
	def _handle_nonplugin_error(self, exc_type, exc_value, exc_tb):
		# Normally, we would like to use sys.__excepthook__ here. But it doesn't
		# work with our "fake" traceback (see _add_missing_frames(...)). The
		# following call avoids this yet produces the same result:
		traceback.print_exception(exc_type, exc_value, exc_tb)
	def _add_missing_frames(self, tb):
		"""
		Let f and h be Python functions and g be a function of Qt. If
			f() -> g() -> h()
		(where "->" means "calls"), and an exception occurs in h(), then the
		associated traceback does not contain f. This can hinder debugging.
		To fix this, we create a "fake" traceback that contains the missing
		entries.

		The code below can be used to reproduce the f() -> g() -> h() problem.
		It opens a window with a button. When you click it, an error occurs
		whose traceback does not include f().

			from PyQt5.QtWidgets import *
			from PyQt5.QtCore import Qt

			class Window(QWidget):
				def __init__(self):
					super().__init__()
					btn = QPushButton('Click me', self)
					btn.clicked.connect(self.f)
				def f(self, _):
					self.inputMethodQuery(Qt.ImAnchorPosition)
				def inputMethodQuery(self, query):
					if query == Qt.ImAnchorPosition:
						# Make Qt call inputMethodQuery(ImCursorPosition).
						# This is our "g()":
						return super().inputMethodQuery(query) # "g()"
					self.h()
				def h(self):
					raise Exception()

			app = QApplication([])
			window = Window()
			window.show()
			app.exec()
		"""
		result = fake_tb(tb.tb_frame, tb.tb_lasti, tb.tb_lineno, tb.tb_next)
		frame = tb.tb_frame.f_back
		while frame:
			result = fake_tb(frame, frame.f_lasti, frame.f_lineno, result)
			frame = frame.f_back
		return result
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
		self, rollbar_token, environment, fman_version, plugin_error_handler
	):
		super().__init__(plugin_error_handler)
		self._rollbar_token = rollbar_token
		self._environment = environment
		self._fman_version = fman_version
		self._user = None
		self._rate_limiter = RateLimiter(60, 10)
	def install(self):
		rollbar.init(
			self._rollbar_token, self._environment,
			code_version=self._fman_version,
			locals={ 'safe_repr': False }
		)
		super().install()
	def set_user(self, user):
		self._user = user
	def _handle_nonplugin_error(self, exc_type, exc_value, exc_tb):
		super()._handle_nonplugin_error(exc_type, exc_value, exc_tb)
		if self._rate_limiter.please():
			request = RollbarRequest(self._user) if self._user else None
			rollbar.report_exc_info(
				(exc_type, exc_value, exc_tb), request, self._extra_data
			)
	@cached_property
	def _extra_data(self):
		return {
			'os': {
				'name': os_.name(),
				'version': os_.version(),
				'distribution': os_.distribution()
			}
		}

class RateLimiter:
	def __init__(self, interval_secs, allowance, time_fn=time):
		self._interval = interval_secs
		self._allowance = allowance
		self._time_fn = time_fn
		self._last_request = time_fn()
		self._num_requests = 0
	def please(self):
		now = self._time_fn()
		if now > self._last_request + self._interval:
			self._num_requests = 0
		if self._num_requests < self._allowance:
			self._num_requests += 1
			self._last_request = now
			return True
		return False

fake_tb = \
	namedtuple('fake_tb', ('tb_frame', 'tb_lasti', 'tb_lineno', 'tb_next'))

RollbarRequest = namedtuple('RollbarRequest', ('user_id',))