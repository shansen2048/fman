from fman.impl.model.mother_fs import MotherFileSystem
from fman_unittest.impl.model import StubFileSystem
from threading import Thread, Lock
from time import sleep
from unittest import TestCase

class MotherFileSystemTest(TestCase):
	def test_exists(self):
		fs = StubFileSystem({
			'a': {}
		})
		cached_fs = MotherFileSystem(fs, None)
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
		cached_fs = MotherFileSystem(fs, None)
		self.assertEqual(['a/b'], cached_fs.listdir('a'))
		cached_fs.delete('a/b')
		self.assertEqual([], cached_fs.listdir('a'))
	def test_rename_updates_pardir(self):
		fs = StubFileSystem({
			'a': { 'isdir': True , 'files': ['a/b']},
			'a/b': {},
			'c': { 'isdir': True }
		})
		cached_fs = MotherFileSystem(fs, None)
		self.assertEqual(['a/b'], cached_fs.listdir('a'))
		self.assertEqual([], cached_fs.listdir('c'))
		cached_fs.rename('a/b', 'c/b')
		self.assertEqual([], cached_fs.listdir('a'))
		self.assertEqual(['c/b'], cached_fs.listdir('c'))
	def test_touch(self):
		fs = StubFileSystem({
			'a': { 'isdir': True }
		})
		cached_fs = MotherFileSystem(fs, None)
		self.assertEqual([], cached_fs.listdir('a'))
		cached_fs.touch('a/b')
		self.assertEqual(['a/b'], cached_fs.listdir('a'))
	def test_mkdir(self):
		fs = StubFileSystem({
			'a': { 'isdir': True }
		})
		cached_fs = MotherFileSystem(fs, None)
		self.assertEqual([], cached_fs.listdir('a'))
		cached_fs.mkdir('a/b')
		self.assertEqual(['a/b'], cached_fs.listdir('a'))
	def test_no_concurrent_isdir_queries(self):
		fs = FileSystemCountingIsdirCalls()
		cached_fs = MotherFileSystem(fs, None)
		_new_thread = lambda: Thread(target=cached_fs.isdir, args=('test',))
		t1, t2 = _new_thread(), _new_thread()
		t1.start()
		t2.start()
		t1.join()
		t2.join()
		self.assertEqual(1, fs.num_isdir_calls)
		self.assertEqual({}, cached_fs._cache_locks, 'Likely memory leak!')
	def test_permission_error(self):
		fs = FileSystemRaisingError()
		cached_fs = MotherFileSystem(fs, None)
		# Put 'foo' in cache:
		cached_fs.isdir('foo')
		with self.assertRaises(PermissionError):
			cached_fs.listdir('foo')

class FileSystemCountingIsdirCalls:
	def __init__(self):
		self.num_isdir_calls = 0
		self._num_isdir_calls_lock = Lock()
	def isdir(self, _):
		with self._num_isdir_calls_lock:
			self.num_isdir_calls += 1
		# Give other threads a chance to run:
		sleep(.1)
		return True

class FileSystemRaisingError:
	def isdir(self, path):
		return True
	def listdir(self, path):
		raise PermissionError(path)