from core import Name, Size, Modified
from core.tests import StubFS
from fman.url import as_url
from fman_unittest.impl.model import StubFileSystem
from unittest import TestCase

class ColumnTest:
	def setUp(self):
		file_system = StubFileSystem({
			'a': {
				'is_dir': False, 'size': 1, 'mtime': 1473339042.0
			},
			'b': {
				'is_dir': False, 'size': 0, 'mtime': 1473339043.0
			},
			'B': {
				'is_dir': False, 'size': 2, 'mtime': 1473339042.0
			},
			'a_dir': {
				'is_dir': True, 'size': 3, 'mtime': 1473339045.0
			},
			'b_dir': {
				'is_dir': True, 'size': 4, 'mtime': 1473339046.0
			}

		})
		self._column = self.column_class(StubFS(file_system))
	def assert_is_less(self, left, right, is_ascending=True):
		self.assertLess(
			self._get_sort_value(left, is_ascending),
			self._get_sort_value(right, is_ascending),
			"%s is not < %s" % (left, right)
		)
	def assert_is_greater(self, left, right, is_ascending=True):
		self.assertGreater(
			self._get_sort_value(left, is_ascending),
			self._get_sort_value(right, is_ascending),
			"%s is not > %s" % (left, right)
		)
	def check_less_than_chain(self, *chain, is_ascending=True):
		for i, left in enumerate(chain[:-1]):
			right = chain[i + 1]
			self.assert_is_less(left, right, is_ascending)
	def _get_sort_value(self, path, is_ascending):
		url = as_url(path, StubFileSystem.scheme)
		return self._column.get_sort_value(url, is_ascending)

class NameTest(ColumnTest, TestCase):

	column_class = Name

	def test_less(self):
		self.assert_is_less('a', 'b')
	def test_greater(self):
		self.assert_is_greater('b', 'a')
	def test_upper_case(self):
		self.assert_is_less('a', 'B')
	def test_directories_before_files(self):
		self.check_less_than_chain('a_dir', 'b_dir', 'a')
	def test_descending(self):
		self.check_less_than_chain(
			'a', 'b', 'a_dir', 'b_dir',
			is_ascending=False
		)

class SizeTest(ColumnTest, TestCase):

	column_class = Size

	def test_less(self):
		self.assert_is_less('b', 'a')
	def test_greater(self):
		self.assert_is_greater('a', 'b')
	def test_descending(self):
		# Qt expects the implementation of less_than to generally be independent
		# of the sort order:
		self.assert_is_less('b', 'a', False)
	def test_directories_by_name_before_files(self):
		self.check_less_than_chain('a_dir', 'b_dir', 'b')
	def test_directories_by_name_before_files_descending(self):
		self.check_less_than_chain(
			'b', 'a', 'b_dir', 'a_dir', is_ascending=False
		)

class ModifiedTest(ColumnTest, TestCase):

	column_class = Modified

	def test_less(self):
		self.assert_is_less('a', 'b')
	def test_greater(self):
		self.assert_is_greater('b', 'a')
	def test_descending(self):
		# Qt expects the implementation of less_than to generally be independent
		# of the sort order:
		self.assert_is_less('a', 'b', False)
	def test_directories_before_files(self):
		self.check_less_than_chain('a_dir', 'b_dir', 'a')