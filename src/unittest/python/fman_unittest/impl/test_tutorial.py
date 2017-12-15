from fbs_runtime.system import is_windows
from fman.impl.tutorial.impl import _get_navigation_steps
from fman.url import as_url, basename, dirname, as_human_readable, join
from os.path import splitdrive
from unittest import skipIf, TestCase

class GetNavigationStepsTest(TestCase):
	def test_self(self):
		self.assertEqual([], _get_navigation_steps(self._root, self._root))
	def test_sub_dir(self):
		self.assertEqual(
			[('open', basename(self._root))],
			_get_navigation_steps(self._root, dirname(self._root))
		)
	def test_go_up(self):
		self.assertEqual(
			[('go up', '')],
			_get_navigation_steps(dirname(self._root), self._root)
		)
	def test_wrong_scheme(self):
		if is_windows():
			root_drive = splitdrive(as_human_readable(self._root))[0] + '\\'
		else:
			root_drive = '/'

		self.assertEqual(
			[('go to', root_drive), ('open', 'test')],
			_get_navigation_steps(join(as_url(root_drive), 'test'), 'null://')
		)
	@skipIf(not is_windows(), 'Skipping Windows-only test')
	def test_switch_drives(self):
		self.assertEqual(
			[('show drives', ''), ('open', 'D:'), ('open', '64Bit')],
			_get_navigation_steps(
				as_url(r'D:\64Bit'), as_url(r'C:\Users\Michael')
			)
		)
	@skipIf(not is_windows(), 'Skipping Windows-only test')
	def test_start_from_drives(self):
		self.assertEqual(
			[('open', 'D:'), ('open', '64Bit')],
			_get_navigation_steps(as_url(r'D:\64Bit'), 'drives://')
		)
	def setUp(self):
		super().setUp()
		self._root = dirname(as_url(__file__))