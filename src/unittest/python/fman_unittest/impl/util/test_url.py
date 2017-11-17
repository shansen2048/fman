from fman.impl.util.url import get_existing_pardir, is_pardir, resolve
from unittest import TestCase

class GetExistingPardirTest(TestCase):
	def test_dir(self):
		dir_ = 'dropbox://Work/fman'
		self._expect(dir_, dir_, {dir_})
	def test_subdir(self):
		subdir = 'dropbox://Work/fman/a'
		pardir = 'dropbox://Work/fman'
		self._expect(pardir, subdir, {pardir})
	def test_subdir_2(self):
		subdir = 'dropbox://Work/fman/a/b'
		pardir = 'dropbox://Work/fman'
		self._expect(pardir, subdir, {pardir})
	def test_no_result(self):
		self.assertIsNone(get_existing_pardir('dropbox://', lambda _: False))
	def _expect(self, expected_result, dir_, dirs):
		is_dir = lambda url: url in dirs
		self.assertEqual(expected_result, get_existing_pardir(dir_, is_dir))

class IsPardirTest(TestCase):
	def test_self(self):
		url = 'file:///home'
		self.assertTrue(is_pardir(url, url))
	def test_pardir(self):
		self.assertTrue(is_pardir('file:///a', 'file:///a/b'))
	def test_pardir_2(self):
		self.assertTrue(is_pardir('file:///a', 'file:///a/b/c'))
	def test_different_scheme(self):
		self.assertFalse(is_pardir('file://C:', 'drives://C:'))
	def test_scheme_root(self):
		self.assertTrue(is_pardir('file://', 'file:///home'))

class ResolveTest(TestCase):
	def test_fine(self):
		url = 'file:///home/a/b'
		self.assertEqual(url, resolve(url))
	def test_trailing_dot(self):
		self.assertEqual('file://a', resolve('file://a/.'))
	def test_single_dot_between(self):
		self.assertEqual('file://a/b', resolve('file://a/./b'))
	def test_trailing_double_dot(self):
		self.assertEqual('file://', resolve('file://a/..'))
	def test_single_dot_only(self):
		self.assertEqual('file://', resolve('file://.'))