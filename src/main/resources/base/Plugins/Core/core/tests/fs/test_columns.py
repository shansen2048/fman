from core.fs import NameColumn, SizeColumn, LastModifiedColumn, \
	TemporaryDirectory
from core.tests import StubFS
from fman.url import as_url
from pathlib import Path
from time import sleep
from unittest import TestCase

class ColumnTest:
	def setUp(self):
		super().setUp()
		self._column = self.column_class(StubFS())
		self._tmp_dir = TemporaryDirectory()
	def tearDown(self):
		self._tmp_dir.cleanup()
		super().tearDown()
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
	def _get_sort_value(self, name, is_ascending):
		url = as_url(Path(self._tmp_dir.name, name))
		return self._column.get_sort_value(url, is_ascending)

class NameColumnTest(ColumnTest, TestCase):

	column_class = NameColumn

	def setUp(self):
		super().setUp()
		for file_name in ('a', 'b', 'C'):
			Path(self._tmp_dir.name, file_name).touch()
		for dir_name in ('a_dir', 'b_dir'):
			Path(self._tmp_dir.name, dir_name).mkdir()
	def test_less(self):
		self.assert_is_less('a', 'b')
	def test_greater(self):
		self.assert_is_greater('b', 'a')
	def test_upper_case(self):
		self.assert_is_less('a', 'C')
	def test_directories_before_files(self):
		self.check_less_than_chain('a_dir', 'b_dir', 'a')
	def test_descending(self):
		self.check_less_than_chain(
			'a', 'b', 'a_dir', 'b_dir',
			is_ascending=False
		)

class SizeColumnTest(ColumnTest, TestCase):

	column_class = SizeColumn

	def setUp(self):
		super().setUp()
		for file_name, size in (('a', 1), ('b', 0)):
			Path(self._tmp_dir.name, file_name).write_bytes(b'a' * size)
		for dir_name in ('a_dir', 'b_dir'):
			Path(self._tmp_dir.name, dir_name).mkdir()
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

	def setUp(self):
		super().setUp()
		a = Path(self._tmp_dir.name, 'a')
		a.touch()
		sleep(.01)
		b = Path(self._tmp_dir.name, 'b')
		b.touch()
		assert b.stat().st_mtime > a.stat().st_mtime
		a_dir = Path(self._tmp_dir.name, 'a_dir')
		a_dir.mkdir()
		sleep(.01)
		b_dir = Path(self._tmp_dir.name, 'b_dir')
		b_dir.mkdir()
		assert b_dir.stat().st_mtime > a_dir.stat().st_mtime
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