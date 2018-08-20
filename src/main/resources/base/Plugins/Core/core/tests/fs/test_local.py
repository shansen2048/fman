from fman import PLATFORM
from core import LocalFileSystem
from unittest import TestCase

class LocalFileSystemTest(TestCase):
	def test_mkdir_root(self):
		with self.assertRaises(FileExistsError):
			self._fs.mkdir('C:' if PLATFORM == 'Windows' else '/')
	def test_iterdir_nonexistent(self):
		root = 'C:/' if PLATFORM == 'Windows' else '/'
		path = root + 'nonexistent'
		with self.assertRaises(FileNotFoundError):
			next(iter(self._fs.iterdir(path)))
	def test_empty_path_does_not_exist(self):
		self.assertFalse(self._fs.exists(''))
	def setUp(self):
		super().setUp()
		self._fs = LocalFileSystem()