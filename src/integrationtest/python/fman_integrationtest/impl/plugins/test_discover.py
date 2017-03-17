from fman.impl.plugins import USER_PLUGIN_NAME
from fman.impl.plugins.discover import find_plugin_dirs
from os import mkdir
from os.path import join, basename
from shutil import rmtree
from tempfile import mkdtemp
from unittest import TestCase

class FindPluginDirsTest(TestCase):
	def test_find_plugins(self):
		plugin_dirs = \
			[self.shipped_plugin, self.installed_plugin, self.user_plugin]
		for plugin_dir in plugin_dirs:
			mkdir(plugin_dir)
		self.assertEqual(
			plugin_dirs,
			find_plugin_dirs(self.shipped_plugins, self.installed_plugins)
		)
	def test_find_plugins_no_user_plugin(self):
		plugin_dirs = [self.shipped_plugin, self.installed_plugin]
		for plugin_dir in plugin_dirs:
			mkdir(plugin_dir)
		self.assertEqual(
			plugin_dirs,
			find_plugin_dirs(self.shipped_plugins, self.installed_plugins)
		)
	def setUp(self):
		self.shipped_plugins = mkdtemp()
		self.installed_plugins = mkdtemp()
		self.shipped_plugin = join(self.shipped_plugins, 'Shipped')
		installed_plugin = 'Very Simple Plugin'
		assert basename(installed_plugin)[0] > USER_PLUGIN_NAME[0], \
			"Please ensure that the name of the installed plugin appears in" \
			"listdir(...) _after_ the User plugin. This lets us test that" \
			"find_plugins(...) does not simply return plugins in the same " \
			"order as listdir(...) but ensures that the User plugin appears " \
			"last."
		self.installed_plugin = join(self.installed_plugins, installed_plugin)
		self.user_plugin = join(self.installed_plugins, USER_PLUGIN_NAME)
	def tearDown(self):
		rmtree(self.shipped_plugins)
		rmtree(self.installed_plugins)
