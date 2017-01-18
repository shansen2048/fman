from fman.util import is_in_subdir
from fman.util.system import is_windows
from os.path import join
from unittest import TestCase, skipIf

class IsInSubdirTest(TestCase):
	def test_direct_subdir(self):
		self.assertTrue(is_in_subdir(join(self.root, 'subdir'), self.root))
	def test_self(self):
		self.assertFalse(is_in_subdir(self.root, self.root))
	def test_nested_subdir(self):
		nested = join(self.root, 'subdir', 'nested')
		self.assertTrue(is_in_subdir(nested, self.root))
	@skipIf(not is_windows(), 'Skipping Windows-only test')
	def test_different_drive_windows(self):
		self.assertFalse(is_in_subdir(r'c:\Dir\Subdir', r'D:\Dir'))
	def setUp(self):
		self.root = r'C:\Dir' if is_windows() else '/Dir'