from fman.util import Signal
from fman.impl.model import SizeColumn, NameColumn, LastModifiedColumn, \
	CachedFileSystem, DiffEntry, ComputeDiff, FileSystemModel
from itertools import chain, combinations
from threading import Thread, Lock
from time import sleep
from unittest import TestCase

class GetMoveDestinationTest(TestCase):
	def test_move_one_row_up(self):
		# Example taken from the Qt docs on QAbstractItemModel#beginMoveRows.
		self.assertEqual(0, FileSystemModel._get_move_destination(2, 0, 1))
	def test_move_one_row_one_step_down(self):
		# Example taken from the Qt docs on QAbstractItemModel#beginMoveRows.
		self.assertEqual(4, FileSystemModel._get_move_destination(2, 3, 1))
	def test_move_multiple_rows_down_overlapping(self):
		self.assertEqual(4, FileSystemModel._get_move_destination(1, 2, 2))
	def test_move_multiple_rows_down_adjacent(self):
		self.assertEqual(5, FileSystemModel._get_move_destination(1, 3, 2))
	def test_move_multiple_rows_far_down(self):
		self.assertEqual(6, FileSystemModel._get_move_destination(1, 4, 2))
	def test_move_multiple_rows_one_up(self):
		self.assertEqual(1, FileSystemModel._get_move_destination(2, 1, 99))
	def test_move_multiple_rows_two_up(self):
		self.assertEqual(0, FileSystemModel._get_move_destination(2, 0, 99))
	def test_move_multiple_rows_far_up(self):
		self.assertEqual(2, FileSystemModel._get_move_destination(5, 2, 2))

class ComputeDiffTest(TestCase):
	def test_empty(self):
		self._check_diff([], [], [])
	def test_same(self):
		rows = [self._a, self._b, self._c]
		self._check_diff(rows, rows, [])
	def test_add_into_empty(self):
		rows = [self._a, self._b]
		self._check_diff([], rows, [(0, 0, 0, rows)])
	def test_insert_before(self):
		base = [self._c]
		extra = [self._a, self._b]
		self._check_diff(base, extra + base, [(0, 0, 0, extra)])
	def test_insert_after(self):
		base = [self._a]
		extra = [self._b, self._c]
		self._check_diff(base, base + extra, [(0, 0, 1, extra)])
	def test_insert_between(self):
		self._check_diff(
			[self._a, self._c],
			[self._a, self._b, self._c],
			[(0, 0, 1, [self._b])]
		)
	def test_reorder_rows(self):
		self._check_diff(
			[self._a, self._b],
			[self._b, self._a],
			[(1, 2, 0, [self._b])]
		)
	def test_powerset_combinations(self, max_num_rows=5):
		for old in _powerset(range(max_num_rows)):
			for new in _powerset(range(max_num_rows)):
				pathify = lambda s: [(str(i), i) for i in s]
				self._check_diff(pathify(old), pathify(new))
	def test_clear(self):
		self._check_diff([self._a, self._b], [], [(0, 2, 0, [])])
	def setUp(self):
		super().setUp()
		self._a = ('a', 1)
		self._b = ('b', 2)
		self._c = ('c', 3)
	def _check_diff(self, old, new, expected_diff_tpls=None):
		diff = ComputeDiff(old, new)()
		old_patched = self._apply_diff(diff, old)
		self.assertEqual(
			new, old_patched,
			'Diff %r for %r -> %r is incorrect!' % (diff, old, new)
		)
		if expected_diff_tpls is not None:
			expected_diff = [DiffEntry(*entry) for entry in expected_diff_tpls]
			self.assertEqual(expected_diff, diff)
	def _apply_diff(self, diff, old):
		result = list(old)
		for entry in diff:
			result = result[:entry.cut_start] + result[entry.cut_end:]
			result = result[:entry.insert_start] + entry.rows + \
					 result[entry.insert_start:]
		return result

def _powerset(iterable):
	s = list(iterable)
	return chain.from_iterable(combinations(s, r) for r in range(len(s) + 1))

class CachedFileSystemTest(TestCase):
	def test_exists(self):
		fs = StubFileSystem({
			'a': {}
		})
		cached_fs = CachedFileSystem(fs, None)
		self.assertTrue(cached_fs.exists('a'))
		self.assertFalse(cached_fs.exists('b'))
		cached_fs.touch('b')
		self.assertTrue(cached_fs.exists('b'))
	def test_delete_removes_from_pardir_cache(self):
		fs = StubFileSystem({
			'a': {
				'isdir': True, 'files': ['a/b']
			},
			'a/b': {}
		})
		cached_fs = CachedFileSystem(fs, None)
		self.assertEqual(['a/b'], cached_fs.listdir('a'))
		cached_fs.delete('a/b')
		self.assertEqual([], cached_fs.listdir('a'))
	def test_rename_updates_pardir(self):
		fs = StubFileSystem({
			'a': { 'isdir': True , 'files': ['a/b']},
			'a/b': {},
			'c': { 'isdir': True }
		})
		cached_fs = CachedFileSystem(fs, None)
		self.assertEqual(['a/b'], cached_fs.listdir('a'))
		self.assertEqual([], cached_fs.listdir('c'))
		cached_fs.rename('a/b', 'c/b')
		self.assertEqual([], cached_fs.listdir('a'))
		self.assertEqual(['c/b'], cached_fs.listdir('c'))
	def test_touch(self):
		fs = StubFileSystem({
			'a': { 'isdir': True }
		})
		cached_fs = CachedFileSystem(fs, None)
		self.assertEqual([], cached_fs.listdir('a'))
		cached_fs.touch('a/b')
		self.assertEqual(['a/b'], cached_fs.listdir('a'))
	def test_mkdir(self):
		fs = StubFileSystem({
			'a': { 'isdir': True }
		})
		cached_fs = CachedFileSystem(fs, None)
		self.assertEqual([], cached_fs.listdir('a'))
		cached_fs.mkdir('a/b')
		self.assertEqual(['a/b'], cached_fs.listdir('a'))
	def test_no_concurrent_isdir_queries(self):
		fs = FileSystemCountingIsdirCalls()
		cached_fs = CachedFileSystem(fs, None)
		_new_thread = lambda: Thread(target=cached_fs.isdir, args=('test',))
		t1, t2 = _new_thread(), _new_thread()
		t1.start()
		t2.start()
		t1.join()
		t2.join()
		self.assertEqual(1, fs.num_isdir_calls)
		self.assertEqual({}, cached_fs._cache_locks, 'Likely memory leak!')

class FileSystemCountingIsdirCalls:
	def __init__(self):
		self.file_changed = Signal()
		self.num_isdir_calls = 0
		self._num_isdir_calls_lock = Lock()
	def isdir(self, _):
		with self._num_isdir_calls_lock:
			self.num_isdir_calls += 1
		# Give other threads a chance to run:
		sleep(.1)
		return True

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
		self._column = self.column_class(self.fs)
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
		return self._column.get_sort_value(path, is_ascending)

class StubFileSystem:
	def __init__(self, items):
		self._items = items
		self.file_changed = Signal()
	def exists(self, item):
		return item in self._items
	def listdir(self, item):
		return self._items[item].get('files', [])
	def isdir(self, item):
		return self._items[item].get('isdir', False)
	def getsize(self, item):
		return self._items[item].get('size', 1)
	def getmtime(self, item):
		return self._items[item].get('mtime', 1473339041.0)
	def touch(self, item):
		self._items[item] = {}
	def mkdir(self, item):
		self._items[item] = { 'isdir': True }
	def rename(self, old_path, new_path):
		self._items[new_path] = self._items.pop(old_path)
	def delete(self, item):
		del self._items[item]

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