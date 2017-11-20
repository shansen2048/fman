from fman_integrationtest.plugin_tests import PluginTest

class CustomFileSystemTest(PluginTest):
	def test_get_default_columns_returning_nonexistent_column(self):
		with self.assertRaises(KeyError) as cm:
			self._left_pane.set_path('nonexistent-col://')
		error_message = cm.exception.args[0]
		self._assert_starts_with(
			error_message,
			"NonexistentColumnFileSystem#get_default_columns(...) returned a "
			"column that does not exist: 'Nonexistent'. Should have been "
		)
	def test_iterdir_not_implemented(self):
		with self.assertRaises(NotImplementedError) as cm:
			self._left_pane.set_path('noiterdir://')
		self.assertEqual(
			'NoIterdirFileSystem does not implement iterdir(...)',
			cm.exception.args[0]
		)
	def _assert_starts_with(self, text, prefix):
		self.assertEqual(prefix, text[:len(prefix)])