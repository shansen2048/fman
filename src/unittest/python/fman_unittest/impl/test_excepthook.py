from fman.impl.excepthook import RateLimiter
from unittest import TestCase

class RateLimiterTest(TestCase):
	def test_allowed_at_start(self):
		self.assertTrue(self._limiter.please())
	def test_exceed_limit(self):
		self.assertTrue(self._limiter.please())
		self.assertTrue(self._limiter.please())
		self.assertFalse(self._limiter.please())
		self._time += 3
		self.assertTrue(self._limiter.please())
		self.assertTrue(self._limiter.please())
		self.assertFalse(self._limiter.please())
	def setUp(self):
		super().setUp()
		self._time = 0
		self._limiter = RateLimiter(
			interval_secs=2, allowance=2, time_fn=lambda: self._time
		)