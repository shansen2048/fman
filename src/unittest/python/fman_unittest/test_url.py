from fman.url import as_file_url
from fman.util.system import  is_windows
from unittest import TestCase
from os.path import join

class AsFileUrlTest(TestCase):
	def test_does_not_escape_space(self):
		root = 'C:\\' if is_windows() else '/'
		self.assertEquals('file:///a b', as_file_url(join(root, 'a b')))