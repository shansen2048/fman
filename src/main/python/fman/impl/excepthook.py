from fbs_runtime.excepthook import Excepthook
from fman.impl.util import os_
from time import time

import sentry_sdk

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

class SentryExcepthook(FmanExcepthook):
	def __init__(
		self, sentry_dsn, environment, fman_version, plugin_error_handler
	):
		super().__init__(plugin_error_handler)
		self._sentry_dsn = sentry_dsn
		self._environment = environment
		self._fman_version = fman_version
		self._rate_limiter = RateLimiter(60, 10)
		# Sentry doesn't give us an easy way to set context information
		# globally, for all threads. This is a problem because #set_user(...)
		# below is called from a separate thread. So we retain a reference to
		# "the" main scope:
		self._sentry_scope = None
	def install(self):
		sentry_sdk.init(
			self._sentry_dsn, release=self._fman_version,
			environment=self._environment,
			attach_stacktrace=True, default_integrations=False
		)
		self._sentry_scope = sentry_sdk.configure_scope().__enter__()
		self._sentry_scope.set_extra('os_name', os_.name())
		self._sentry_scope.set_extra('os_version', os_.version())
		self._sentry_scope.set_extra('os_distribution', os_.distribution())
		super().install()
	def set_user(self, user):
		self._sentry_scope.user = {'id': user}
	def _handle_nonplugin_error(self, exc_type, exc_value, exc_tb):
		super()._handle_nonplugin_error(exc_type, exc_value, exc_tb)
		if self._rate_limiter.please():
			tb = self._add_missing_frames(exc_tb) if exc_tb else exc_tb
			sentry_sdk.capture_exception((exc_type, exc_value, tb))

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