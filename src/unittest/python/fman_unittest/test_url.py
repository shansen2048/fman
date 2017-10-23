from fman.url import as_file_url
from fman.util.system import  is_windows
from unittest import TestCase

class AsFileUrlTest(TestCase):
	def test_does_not_escape_space(self):
		if is_windows():
			self.assertEquals('file://C:/a b', as_file_url(r'C:\a b'))
		else:
			self.assertEquals('file:///a b', as_file_url('/a b'))