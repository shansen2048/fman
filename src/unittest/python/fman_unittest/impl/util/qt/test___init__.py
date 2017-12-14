from fman.impl.util.qt import as_qurl, from_qurl
from fman.impl.util.system import is_windows
from unittest import TestCase

class AsFromQurlTest(TestCase):
	def test_file_url(self):
		url = 'file://C:/test' if is_windows() else 'file:///test'
		self._check(url)
	def test_zip_url(self):
		url = 'zip://C:/test.zip' if is_windows() else 'zip:///test.zip'
		self._check(url)
	def _check(self, url):
		self.assertEqual(url, from_qurl(as_qurl(url)))