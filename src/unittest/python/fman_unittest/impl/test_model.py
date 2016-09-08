from fman.impl.model import SizeColumn, NameColumn, LastModifiedColumn
from PyQt5.QtCore import QDateTime
from unittest import TestCase

class StubFileInfo:
	def __init__(self, file_name, is_dir, size, last_modified_tpl):
		self._file_name = file_name
		self._is_dir = is_dir
		self._size = size
		self._last_modified = QDateTime(*last_modified_tpl)
	def fileName(self):
		return self._file_name
	def isDir(self):
		return self._is_dir
	def size(self):
		return self._size
	def lastModified(self):
		return self._last_modified

class ColumnTest:
	def setUp(self):
		self.a = StubFileInfo('a', False, 1, (2016, 9, 8, 14, 50, 42))
		self.b = StubFileInfo('b', False, 0, (2016, 9, 8, 14, 50, 43))
		self.B = StubFileInfo('B', False, 2, (2016, 9, 8, 14, 50, 42))
		self.a_dir = StubFileInfo('a', True, 3, (2016, 9, 8, 14, 50, 45))
		self.b_dir = StubFileInfo('b', True, 4, (2016, 9, 8, 14, 50, 46))
		self.column = None
	def assert_is_less(self, left, right, is_ascending=True):
		self.assertTrue(self.column.less_than(left, right, is_ascending))
	def assert_is_greater(self, left, right, is_ascending=True):
		self.assertFalse(self.column.less_than(left, right, is_ascending))
	def check_less_than_chain(self, *chain, is_ascending=True):
		for i, left in enumerate(chain[:-1]):
			right = chain[i + 1]
			self.assert_is_less(left, right, is_ascending)

class NameColumnTest(ColumnTest, TestCase):
	def setUp(self):
		super().setUp()
		self.column = NameColumn
	def test_less(self):
		self.assert_is_less(self.a, self.b)
	def test_greater(self):
		self.assert_is_greater(self.b, self.a)
	def test_upper_case(self):
		self.assert_is_less(self.a, self.B)
	def test_directories_before_files(self):
		self.check_less_than_chain(self.a_dir, self.b_dir, self.a)
	def test_descending(self):
		self.check_less_than_chain(
			self.a, self.b, self.a_dir, self.b_dir,
			is_ascending=False
		)

class SizeColumnTest(ColumnTest, TestCase):
	def setUp(self):
		super().setUp()
		self.column = SizeColumn
	def test_less(self):
		self.assert_is_less(self.b, self.a)
	def test_greater(self):
		self.assert_is_greater(self.a, self.b)
	def test_descending(self):
		# Qt expects the implementation of less_than to generally be independent
		# of the sort order:
		self.assert_is_less(self.b, self.a, False)
	def test_directories_by_name_before_files(self):
		self.check_less_than_chain(self.a_dir, self.b_dir, self.b)
	def test_directories_by_name_before_files_descending(self):
		self.check_less_than_chain(
			self.b, self.a, self.b_dir, self.a_dir,
			is_ascending=False
		)

class LastModifiedColumnTest(ColumnTest, TestCase):
	def setUp(self):
		super().setUp()
		self.column = LastModifiedColumn
	def test_less(self):
		self.assert_is_less(self.a, self.b)
	def test_greater(self):
		self.assert_is_greater(self.b, self.a)
	def test_descending(self):
		# Qt expects the implementation of less_than to generally be independent
		# of the sort order:
		self.assert_is_less(self.a, self.b, False)
	def test_directories_before_files(self):
		self.check_less_than_chain(self.a_dir, self.b_dir, self.a)