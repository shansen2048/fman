from fman.impl.util.system import  is_windows
from fman.url import as_url, dirname, relpath, as_human_readable
from unittest import TestCase

class AsFileUrlTest(TestCase):
	def test_does_not_escape_space(self):
		if is_windows():
			self.assertEqual('file://C:/a b', as_url(r'C:\a b'))
		else:
			self.assertEqual('file:///a b', as_url('/a b'))
	def test_root(self):
		if is_windows():
			self.assertEqual('file://C:/', as_url('C:\\'))
		else:
			self.assertEqual('file:///', as_url('/'))

class AsHumanReadableTest(TestCase):
	def test_normal_file_url(self):
		path = r'C:\Users\Michael' if is_windows() else '/home/michael'
		self.assertEqual(path, as_human_readable(as_url(path)))
	def test_non_file_url(self):
		url = 'https://fman.io/docs'
		self.assertEqual(url, as_human_readable(url))
	def test_root(self):
		root = 'C:\\' if is_windows() else '/'
		self.assertEqual(root, as_human_readable(as_url(root)))

class DirnameTest(TestCase):
	def test_root_windows(self):
		self.assertEqual('drives://', dirname('drives://C:'))
	def test_root_unix(self):
		self.assertEqual('file://', dirname('file:///'))
	def test_top_level_folder_unix(self):
		self.assertEqual('file:///', dirname('file:///home'))
	def test_scheme_only(self):
		self.assertEqual('file://', dirname('file://'))

class RelpathTest(TestCase):
	"""
	Most of these tests are taken from the original implementation:
	https://stackoverflow.com/a/7469728/1839209.
	"""
	def test_parent(self):
		self._check(
			'http://www.example.com/foo',
			'http://www.example.com/bar/baz',
			'../../foo'
		),
	def test_self(self):
		self._check('http://google.com', 'http://google.com', '.'),
	def test_from_self_slash(self):
		self._check('http://google.com', 'http://google.com/', '.'),
	def test_to_self_slash(self):
		self._check('http://google.com/', 'http://google.com', '.'),
	def test_self_slash(self):
		self._check('http://google.com/', 'http://google.com/', '.'),
	def test_same_dir(self):
		self._check(
			'http://google.com/index.html',
			'http://google.com',
			'index.html'
		),
	def test_same_dir_slash(self):
		self._check(
			'http://google.com/index.html',
			'http://google.com/',
			'index.html'
		),
	def test_same_file(self):
		self._check(
			'http://google.com/index.html',
			'http://google.com/index.html',
			'.'
		)
	def test_file_in_dir(self):
		self._check('file:///a/b.txt', 'file:///a', 'b.txt')
	def _check(self, target, base, expected):
		self.assertEqual(expected, relpath(target, base))