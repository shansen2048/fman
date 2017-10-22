from fman.impl.plugins.mother_fs import MotherFileSystem
from fman_unittest.impl.model import StubFileSystem
from threading import Thread, Lock
from time import sleep
from unittest import TestCase

class MotherFileSystemTest(TestCase):
	def test_exists(self):
		fs = StubFileSystem({
			'a': {}
		})
		cached_fs = MotherFileSystem([fs], None)
		self.assertTrue(cached_fs.exists('stub://a'))
		self.assertFalse(cached_fs.exists('stub://b'))
		cached_fs.touch('stub://b')
		self.assertTrue(cached_fs.exists('stub://b'))
	def test_delete_removes_from_pardir_cache(self):
		fs = StubFileSystem({
			'a': {
				'isdir': True, 'files': ['a/b']
			},
			'a/b': {}
		})
		cached_fs = MotherFileSystem([fs], None)
		self.assertEqual(['stub://a/b'], cached_fs.listdir('stub://a'))
		cached_fs.delete('stub://a/b')
		self.assertEqual([], cached_fs.listdir('stub://a'))
	def test_rename_updates_pardir(self):
		fs = StubFileSystem({
			'a': { 'isdir': True , 'files': ['a/b']},
			'a/b': {},
			'c': { 'isdir': True }
		})
		cached_fs = MotherFileSystem([fs], None)
		self.assertEqual(['stub://a/b'], cached_fs.listdir('stub://a'))
		self.assertEqual([], cached_fs.listdir('stub://c'))
		cached_fs.rename('stub://a/b', 'stub://c/b')
		self.assertEqual([], cached_fs.listdir('stub://a'))
		self.assertEqual(['stub://c/b'], cached_fs.listdir('stub://c'))
	def test_touch(self):
		fs = StubFileSystem({
			'a': { 'isdir': True }
		})
		cached_fs = MotherFileSystem([fs], None)
		self.assertEqual([], cached_fs.listdir('stub://a'))
		cached_fs.touch('stub://a/b')
		self.assertEqual(['stub://a/b'], cached_fs.listdir('stub://a'))
	def test_mkdir(self):
		fs = StubFileSystem({
			'a': { 'isdir': True }
		})
		cached_fs = MotherFileSystem([fs], None)
		self.assertEqual([], cached_fs.listdir('stub://a'))
		cached_fs.mkdir('stub://a/b')
		self.assertEqual(['stub://a/b'], cached_fs.listdir('stub://a'))
	def test_no_concurrent_isdir_queries(self):
		fs = FileSystemCountingIsdirCalls()
		cached_fs = MotherFileSystem([fs], None)
		def _new_thread():
			return Thread(target=cached_fs.isdir, args=('fscic://test',))
		t1, t2 = _new_thread(), _new_thread()
		t1.start()
		t2.start()
		t1.join()
		t2.join()
		self.assertEqual(1, fs.num_isdir_calls)
		self.assertEqual({}, cached_fs._cache_locks, 'Likely memory leak!')
	def test_permission_error(self):
		fs = FileSystemRaisingError()
		cached_fs = MotherFileSystem([fs], None)
		# Put 'foo' in cache:
		cached_fs.isdir('fsre://foo')
		with self.assertRaises(PermissionError):
			cached_fs.listdir('fsre://foo')

class FileSystemCountingIsdirCalls:

	scheme = 'fscic://'

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

	scheme = 'fsre://'

	def isdir(self, path):
		return True
	def listdir(self, path):
		raise PermissionError(path)