from contextlib import contextmanager
from core import Name, Size
from fman.impl.model import SortedFileSystemModel
from fman.impl.plugins.builtin import NullFileSystem, NullColumn
from fman.impl.plugins.mother_fs import MotherFileSystem
from fman.impl.util.qt import connect_once
from fman.impl.util.qt.thread import run_in_main_thread
from fman_unittest.impl.model import StubFileSystem
from threading import Event

import sys

class SortedFileSystemModelAT: # Instantiated in fman_integrationtest.test_qt
	def test_location_after_init(self):
		self.assertEqual('null://', self._model.get_location())
	def test_set_location(self):
		loaded = Event()
		self._model.set_location('stub://', callback=loaded.set)
		self.assertEqual('stub://', self._model.get_location())
		loaded.wait()
		self._expect_data([('dir', ''), ('file', '13 B')])
	def test_remove_current_dir(self):
		self._set_location('stub://dir')
		with self._wait_until_loaded():
			self._fs.delete('stub://dir')
		self.assertEqual('stub://', self._model.get_location())
	def test_remove_root(self):
		self._set_location('stub://dir')
		with self._wait_until_loaded():
			self._fs.remove_child('stub://')
		self.assertEqual('null://', self._model.get_location())
	def _set_location(self, location):
		loaded = Event()
		self._model.set_location(location, callback=loaded.set)
		loaded.wait()
	def _expect_data(self, expected):
		self.assertEqual(len(expected), self._model.rowCount())
		self.assertEqual(
			len(expected[0]) if expected else 0, self._model.columnCount()
		)
		m = self._model
		actual = [
			tuple(m.data(m.index(row, col)) for col in range(m.columnCount()))
			for row in range(m.rowCount())
		]
		self.assertEqual(expected, actual)
	@contextmanager
	def _wait_until_loaded(self):
		loaded = Event()
		run_in_main_thread(connect_once)(
			self._model.location_loaded, lambda _: loaded.set()
		)
		yield
		timeout = None if _is_debugging() else .2
		if not loaded.wait(timeout=timeout):
			self.fail('Timeout expired while waiting to location to be loaded.')
	def setUp(self):
		super().setUp()
		self._fs = MotherFileSystem(StubIconProvider())
		self._fs.add_child('null://', NullFileSystem())
		self._register_column(NullColumn())
		self._fs.add_child('stub://', StubFileSystem({
			'': {'is_dir': True, 'files': ['dir', 'file']},
			'dir': {'is_dir': True, 'files': ['subdir']},
			'dir/subdir': {'is_dir': True},
			'file': {'is_dir': False, 'size': 13}
		}, default_columns=('core.Name', 'core.Size')))
		self._register_column(Name(self._fs))
		self._register_column(Size(self._fs))
		self._model = self.run_in_app(
			SortedFileSystemModel, None, self._fs, 'null://'
		)
	def _register_column(self, instance):
		self._fs.register_column(instance.get_qualified_name(), instance)

def _is_debugging():
	return bool(sys.gettrace())

class StubIconProvider:
	def get_icon(self, url):
		return None