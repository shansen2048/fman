from fbs_runtime.system import is_windows
from fman.impl.onboarding.tutorial import _get_navigation_steps
from fman.url import as_url, basename, dirname, as_human_readable, join
from os.path import splitdrive
from unittest import skipIf, TestCase

class GetNavigationStepsTest(TestCase):
	def test_self(self):
		self.assertEqual([], _get_navigation_steps(self._root, self._root))
	def test_sub_dir(self):
		self.assertEqual(
			[('open', basename(dirname(self._root))),
			 ('open', basename(self._root))],
			_get_navigation_steps(self._root, dirname(dirname(self._root)))
		)
	def test_go_up(self):
		self.assertEqual(
			[('go up', ''), ('open', 'util')],
			_get_navigation_steps(join(dirname(self._root), 'util'), self._root)
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
	@skipIf(not is_windows(), 'Skipping Windows-only test')
	def test_network_share(self):
		from core.fs.local.windows.drives import DrivesFileSystem
		self.assertEqual(
			[('show drives', ''), ('open', DrivesFileSystem.NETWORK),
			 ('open', 'SERVER'), ('open', 'Folder')],
			_get_navigation_steps(
				as_url(r'\\SERVER\Folder'), as_url(r'C:\Users\Michael')
			)
		)
		self.assertEqual(
			[('open', 'SERVER'), ('open', 'Folder')],
			_get_navigation_steps(as_url(r'\\SERVER\Folder'), 'network://')
		)
		# Say the user accidentally opened the wrong server:
		self.assertEqual(
			[('go up', ''), ('open', 'B'), ('open', 'Folder')],
			_get_navigation_steps(as_url(r'\\B\Folder'), 'network://A')
		)

	def test_hidden_directory(self):
		is_hidden = lambda url: True
		dst_url = self._root
		src_url = dirname(dst_url)
		dir_name = basename(dst_url)
		self.assertEqual(
			[('toggle hidden files', dir_name), ('open', dir_name)],
			_get_navigation_steps(dst_url, src_url, is_hidden, False)
		)
	def setUp(self):
		super().setUp()
		self._root = dirname(as_url(__file__))