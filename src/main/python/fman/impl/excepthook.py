from collections import namedtuple
from fbs_runtime.application_context import cached_property
from fbs_runtime.excepthook import Excepthook
from fman.impl.util import os_
from time import time

import rollbar

class FmanExcepthook(Excepthook):
	def __init__(self, plugin_error_handler):
		self._plugin_error_handler = plugin_error_handler
	def set_user(self, user):
		pass
	def __call__(self, exc_type, exc_value, exc_tb):
		is_plugin_error = self._plugin_error_handler.handle(exc_tb)
		if not is_plugin_error:
			self._handle_nonplugin_error(exc_type, exc_value, exc_tb)
	def _handle_nonplugin_error(self, exc_type, exc_value, exc_tb):
			super().__call__(exc_type, exc_value, exc_tb)

class RollbarExcepthook(FmanExcepthook):
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
		self._interval_start = time_fn()
		self._num_requests = 0
	def please(self):
		now = self._time_fn()
		if now > self._interval_start + self._interval:
			self._num_requests = 0
			self._interval_start = now
		if self._num_requests < self._allowance:
			self._num_requests += 1
			return True
		return False

fake_tb = \
	namedtuple('fake_tb', ('tb_frame', 'tb_lasti', 'tb_lineno', 'tb_next'))

RollbarRequest = namedtuple('RollbarRequest', ('user_id',))