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
		mother_fs = self._create_mother_fs(fs)
		self.assertTrue(mother_fs.exists('stub://a'))
		self.assertFalse(mother_fs.exists('stub://b'))
		mother_fs.touch('stub://b')
		self.assertTrue(mother_fs.exists('stub://b'))
	def test_delete_removes_from_pardir_cache(self):
		fs = StubFileSystem({
			'a': {
				'is_dir': True, 'files': ['b']
			},
			'a/b': {}
		})
		mother_fs = self._create_mother_fs(fs)
		self.assertEqual(['b'], list(mother_fs.iterdir('stub://a')))
		mother_fs.delete('stub://a/b')
		self.assertEqual([], list(mother_fs.iterdir('stub://a')))
		self.assertFalse(mother_fs.exists('stub://a/b'))
	def test_delete_removes_children(self):
		fs = StubFileSystem({
			'a': {
				'is_dir': True, 'files': ['b']
			},
			'a/b': {}
		})
		mother_fs = self._create_mother_fs(fs)
		# Put in cache:
		mother_fs.is_dir('stub://a/b')
		mother_fs.delete('stub://a')
		self.assertFalse(mother_fs.exists('stub://a/b'))
	def test_move_updates_pardir(self):
		fs = StubFileSystem({
			'a': { 'is_dir': True , 'files': ['b']},
			'a/b': {},
			'c': { 'is_dir': True }
		})
		mother_fs = self._create_mother_fs(fs)
		self.assertEqual(['b'], list(mother_fs.iterdir('stub://a')))
		self.assertEqual([], list(mother_fs.iterdir('stub://c')))
		mother_fs.move('stub://a/b', 'stub://c/b')
		self.assertEqual([], list(mother_fs.iterdir('stub://a')))
		self.assertEqual(['b'], list(mother_fs.iterdir('stub://c')))
	def test_touch(self):
		fs = StubFileSystem({
			'a': { 'is_dir': True }
		})
		mother_fs = self._create_mother_fs(fs)
		self.assertEqual([], list(mother_fs.iterdir('stub://a')))
		mother_fs.touch('stub://a/b')
		self.assertEqual(['b'], list(mother_fs.iterdir('stub://a')))
	def test_mkdir(self):
		fs = StubFileSystem({
			'a': { 'is_dir': True }
		})
		mother_fs = self._create_mother_fs(fs)
		self.assertEqual([], list(mother_fs.iterdir('stub://a')))
		mother_fs.mkdir('stub://a/b')
		self.assertEqual(['b'], list(mother_fs.iterdir('stub://a')))
	def test_no_concurrent_is_dir_queries(self):
		fs = FileSystemCountingIsdirCalls()
		mother_fs = self._create_mother_fs(fs)
		def _new_thread():
			return Thread(target=mother_fs.is_dir, args=('fscic://test',))
		t1, t2 = _new_thread(), _new_thread()
		t1.start()
		t2.start()
		t1.join()
		t2.join()
		self.assertEqual(1, fs.num_is_dir_calls)
		self.assertEqual({}, mother_fs._cache_locks, 'Likely memory leak!')
	def test_permission_error(self):
		fs = FileSystemRaisingError()
		mother_fs = self._create_mother_fs(fs)
		# Put 'foo' in cache:
		mother_fs.is_dir('fsre://foo')
		with self.assertRaises(PermissionError):
			mother_fs.iterdir('fsre://foo')
	def test_is_dir_file(self):
		fs = StubFileSystem({
			'a': {}
		})
		mother_fs = self._create_mother_fs(fs)
		self.assertFalse(mother_fs.is_dir('stub://a'))
	def test_is_dir_nonexistent(self):
		fs = StubFileSystem({})
		mother_fs = self._create_mother_fs(fs)
		url = 'stub://non-existent'
		with self.assertRaises(FileNotFoundError):
			mother_fs.is_dir(url)
		self.assertFalse(mother_fs.exists(url))
		mother_fs.mkdir(url)
		self.assertTrue(mother_fs.is_dir(url))
	def test_remove_child(self):
		fs = StubFileSystem({
			'a': {'is_dir': True}
		})
		mother_fs = self._create_mother_fs(fs)
		self.assertTrue(mother_fs.is_dir('stub://a'))
		mother_fs.remove_child(fs.scheme)
		mother_fs.add_child(fs.scheme, StubFileSystem({}))
		with self.assertRaises(FileNotFoundError):
			mother_fs.is_dir('stub://a')
	def test_mkdir_triggers_file_added(self):
		mother_fs = self._create_mother_fs(StubFileSystem({}))
		url = 'stub://test'
		with self.assertRaises(FileNotFoundError):
			# This should not put `url` in cache:
			mother_fs.is_dir(url)
		files_added = []
		def on_file_added(url_):
			files_added.append(url_)
		mother_fs.file_added.add_callback(on_file_added)
		mother_fs.mkdir(url)
		self.assertEqual([url], files_added)
	def test_relative_paths(self):
		mother_fs = self._create_mother_fs(StubFileSystem({
			'a': {'is_dir': True},
			'a/b': {'is_dir': True}
		}))
		self.assertTrue(mother_fs.is_dir('stub://a/b/..'))
		mother_fs.move('stub://a', 'stub://b')
		with self.assertRaises(FileNotFoundError):
			mother_fs.is_dir('stub://a/b/..')
		mother_fs.touch('stub://a/../c')
		self.assertTrue(mother_fs.exists('stub://c'))
		mother_fs.mkdir('stub://a/../dir')
		self.assertTrue(mother_fs.is_dir('stub://a/../dir'))
		self.assertTrue(mother_fs.is_dir('stub://dir'))
		mother_fs.move('stub://a/b', 'stub://a/../b')
		self.assertTrue(mother_fs.exists('stub://b'))
	def _create_mother_fs(self, fs):
		result = MotherFileSystem(None)
		result.add_child(fs.scheme, fs)
		return result

class FileSystemCountingIsdirCalls:

	scheme = 'fscic://'

	def __init__(self):
		self.num_is_dir_calls = 0
		self._num_is_dir_calls_lock = Lock()
	def is_dir(self, _):
		with self._num_is_dir_calls_lock:
			self.num_is_dir_calls += 1
		# Give other threads a chance to run:
		sleep(.1)
		return True

class FileSystemRaisingError:

	scheme = 'fsre://'

	def is_dir(self, path):
		return True
	def iterdir(self, path):
		raise PermissionError(path)