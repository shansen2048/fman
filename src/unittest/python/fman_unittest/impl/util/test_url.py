from unittest import TestCase
from fman.impl.util.url import get_existing_pardir

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