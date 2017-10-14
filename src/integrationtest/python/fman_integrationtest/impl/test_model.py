from fman.impl.model import IconProvider
from fman_integrationtest import get_resource
from unittest import TestCase

class IconProviderTest(TestCase):
	def test_folder_default(self):
		self._check_icon('normal folder', True, 'default_folder.svg')
	def test_file_default(self):
		self._check_icon('Some file', False, 'default_file.svg')
	def test_pdf(self):
		self._check_icon('Report.pdf', False, 'pdf.svg')
	def test_png_icon(self):
		self._check_icon('Extension.fig', False, 'matlab.png')
	def test_file_exact(self):
		self._check_icon('.gitignore', False, 'git.svg')
		self._check_icon('foo.gitignore', False, 'default_file.svg')
	def test_extension_uppercase(self):
		self._check_icon('Report.PDF', False, 'pdf.svg')
	def _check_icon(self, file_name, is_dir, icon):
		self.assertEqual(icon, self._provider._get_icon_name(file_name, is_dir))
	def setUp(self):
		self._provider = IconProvider(get_resource('Icons.json'), None)