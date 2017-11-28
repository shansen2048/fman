from fman.impl.util.qt import Task, as_qurl, from_qurl
from fman.impl.util.system import is_windows
from unittest import TestCase

class TaskTest(TestCase):
	def test_simple_run(self):
		args = (1,)
		kwargs = {'optional': True}
		def f(*args, **kwargs):
			return args, kwargs
		task = Task(f, args, kwargs)
		task()
		self.assertEqual((args, kwargs), task.result)
	def test_raising_exception(self):
		exception = Exception()
		def raise_exception():
			raise exception
		task = Task(raise_exception, (), {})
		task()
		with self.assertRaises(Exception) as cm:
			task.result
		self.assertIs(exception, cm.exception)

class AsFromQurlTest(TestCase):
	def test_file_url(self):
		url = 'file://C:/test' if is_windows() else 'file:///test'
		self._check(url)
	def test_zip_url(self):
		url = 'zip://C:/test.zip' if is_windows() else 'zip:///test.zip'
		self._check(url)
	def _check(self, url):
		self.assertEqual(url, from_qurl(as_qurl(url)))