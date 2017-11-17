from fman.impl.util import system
from fman.impl.util.path import make_absolute
from os.path import join, expanduser
from unittest import TestCase, skipUnless

class MakeAbsoluteTest(TestCase):
	def test_dot(self):
		self.assertEqual(self.cwd, self._make_absolute('.'))
	def test_home_dir(self, sep='/'):
		self.assertEqual(
			join(expanduser('~'), 'foo', 'test.txt'),
			self._make_absolute(sep.join(['~', 'foo', 'test.txt']))
		)
	@skipUnless(system.is_windows(), 'Only run this test on Windows')
	def test_home_dir_backslash(self):
		self.test_home_dir(sep='\\')
	@skipUnless(system.is_windows(), 'Only run this test on Windows')
	def test_c_drive_no_backslash(self):
		self.assertEqual('C:\\', self._make_absolute('C:'))
	def setUp(self):
		super().setUp()
		self.cwd = self._make_path('foo/bar')
	def _make_absolute(self, path):
		return make_absolute(path, self.cwd)
	def _make_path(self, path):
		return join(self._get_root_dir(), *path.split('/'))
	def _get_root_dir(self):
		return 'C:\\' if system.is_windows() else '/'