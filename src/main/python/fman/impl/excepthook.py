from fbs_runtime.excepthook import ExceptionHandler
from fman.impl.util import os_
from time import time

import sentry_sdk

class SentryExceptionHandler(ExceptionHandler):
	def __init__(self, dsn, environment, fman_version):
		super().__init__()
		self._dsn = dsn
		self._environment = environment
		self._app_version = fman_version
		self._rate_limiter = RateLimiter(60, 10)
		# Sentry doesn't give us an easy way to set context information
		# globally, for all threads. This is a problem because #set_user(...)
		# below is called from a separate thread. So we retain a reference to
		# "the" main scope:
		self._sentry_scope = None
	def init(self):
		sentry_sdk.init(
			self._dsn, release=self._app_version, environment=self._environment,
			attach_stacktrace=True, default_integrations=False
		)
		self._sentry_scope = sentry_sdk.configure_scope().__enter__()
		self._sentry_scope.set_extra('os_name', os_.name())
		self._sentry_scope.set_extra('os_version', os_.version())
		self._sentry_scope.set_extra('os_distribution', os_.distribution())
	def handle(self, exc_type, exc_value, enriched_tb):
		if self._rate_limiter.please():
			sentry_sdk.capture_exception((exc_type, exc_value, enriched_tb))
	def set_user(self, user):
		self._sentry_scope.user = {'id': user}

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