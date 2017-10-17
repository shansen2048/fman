from fman.impl.model import CachedFileSystem, FileSystemModel
from fman.util import Signal
from fman_unittest.impl.model import StubFileSystem
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