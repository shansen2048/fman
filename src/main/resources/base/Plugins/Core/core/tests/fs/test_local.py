from fman import PLATFORM
from core import LocalFileSystem
from unittest import TestCase

class LocalFileSystemTest(TestCase):
	def test_mkdir_root(self):
		with self.assertRaises(FileExistsError):
			self._fs.mkdir('C:' if PLATFORM == 'Windows' else '/')
	def setUp(self):
		super().setUp()
		self._fs = LocalFileSystem()