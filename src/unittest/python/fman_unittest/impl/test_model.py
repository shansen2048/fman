from fman.impl.model import SizeColumn, NameColumn, LastModifiedColumn
from unittest import TestCase

class ColumnTest:
	def setUp(self):
		self.fs = StubFileSystem({
			'a': {
				'isdir': False, 'size': 1, 'mtime': 1473339042.0
			},
			'b': {
				'isdir': False, 'size': 0, 'mtime': 1473339043.0
			},
			'B': {
				'isdir': False, 'size': 2, 'mtime': 1473339042.0
			},
			'a_dir': {
				'isdir': True, 'size': 3, 'mtime': 1473339045.0
			},
			'b_dir': {
				'isdir': True, 'size': 4, 'mtime': 1473339046.0
			}

		})
		self.column = self.column_class(self.fs)
	def assert_is_less(self, left, right, is_ascending=True):
		self.assertTrue(self.column.less_than(left, right, is_ascending))
	def assert_is_greater(self, left, right, is_ascending=True):
		self.assertFalse(self.column.less_than(left, right, is_ascending))
	def check_less_than_chain(self, *chain, is_ascending=True):
		for i, left in enumerate(chain[:-1]):
			right = chain[i + 1]
			self.assert_is_less(left, right, is_ascending)

class StubFileSystem:
	def __init__(self, items):
		self._items = items
	def isdir(self, item):
		return self._items[item]['isdir']
	def getsize(self, item):
		return self._items[item]['size']
	def getmtime(self, item):
		return self._items[item]['mtime']

class NameColumnTest(ColumnTest, TestCase):

	column_class = NameColumn

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

class SizeColumnTest(ColumnTest, TestCase):

	column_class = SizeColumn

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

class LastModifiedColumnTest(ColumnTest, TestCase):

	column_class = LastModifiedColumn

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