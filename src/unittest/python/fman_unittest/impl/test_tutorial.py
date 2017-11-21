from fman.impl.tutorial.impl import _get_navigation_steps
from fman.impl.util.system import is_windows
from unittest import skipIf, TestCase
from os.path import dirname, basename

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
	@skipIf(not is_windows(), 'Skipping Windows-only test')
	def test_switch_drives(self):
		self.assertEqual(
			[('show drives', ''), ('open', 'D:'), ('open', '64Bit')],
			_get_navigation_steps(r'D:\64Bit', r'C:\Users\Michael')
		)
	@skipIf(not is_windows(), 'Skipping Windows-only test')
	def test_my_computer(self):
		self.assertEqual(
			[('open', 'D:'), ('open', '64Bit')],
			_get_navigation_steps(r'D:\64Bit', '')
		)
	def setUp(self):
		super().setUp()
		self._root = dirname(__file__)