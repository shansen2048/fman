from fman.impl.session import SessionManager
from fman.util import system
from os.path import join, expanduser
from unittest import TestCase, skipUnless

class SessionManagerTest(TestCase):
	def test_make_absolute_dot(self):
		self.assertEquals(self.cwd, self._make_absolute('.'))
	def test_make_absolute_home_dir(self, sep='/'):
		self.assertEquals(
			join(expanduser('~'), 'foo', 'test.txt'),
			self._make_absolute(sep.join(['~', 'foo', 'test.txt']))
		)
	@skipUnless(system.is_windows(), 'Only run this test on Windows')
	def test_make_absolute_home_dir_backslash(self):
		self.test_make_absolute_home_dir(sep='\\')
	@skipUnless(system.is_windows(), 'Only run this test on Windows')
	def test_make_absolute_c_drive_no_backslash(self):
		self.assertEquals('C:\\', self._make_absolute('C:'))
	def setUp(self):
		super().setUp()
		self.instance = SessionManager('', '')
		self.cwd = self._make_path('foo/bar')
	def _make_absolute(self, path):
		return self.instance._make_absolute(path, self.cwd)
	def _make_path(self, path):
		return join(self._get_root_dir(), *path.split('/'))
	def _get_root_dir(self):
		return 'C:\\' if system.is_windows() else '/'