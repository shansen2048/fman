from contextlib import contextmanager
from core import Name, Size
from fman.impl.model import SortedFileSystemModel
from fman.impl.plugins.builtin import NullFileSystem, NullColumn
from fman.impl.plugins.mother_fs import MotherFileSystem
from fman.impl.util.qt import connect_once, DisplayRole, DecorationRole
from fman.impl.util.qt.thread import run_in_main_thread
from fman.url import splitscheme
from fman_unittest.impl.model import StubFileSystem
from PyQt5.QtCore import Qt
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
		self._expect_column_headers(['Name', 'Size'])
		self._expect_data([('dir', ''), ('file', '13 B')])
		self._expect_data(
			[(self._folder_icon, None), (self._file_icon, None)],
			DecorationRole
		)
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
	def _expect_data(self, expected, role=DisplayRole):
		self.assertEqual(len(expected), self._model.rowCount())
		self.assertEqual(
			len(expected[0]) if expected else 0, self._model.columnCount()
		)
		model = self._model
		actual = []
		for row in range(self._model.rowCount()):
			actual.append(tuple(
				model.data(model.index(row, col), role)
				for col in range(self._model.columnCount())
			))
		self.assertEqual(expected, actual)
	def _expect_column_headers(self, expected):
		actual = [
			self._model.headerData(column, Qt.Horizontal)
			for column in range(self._model.columnCount())
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
		# N.B.: Normally we should have QIcon instances here. But they don't
		# seem to work well with ==. So use strings instead:
		folder_icon = '<folder icon>'
		file_icon = '<file icon>'
		files = {
			'': {'is_dir': True, 'files': ['dir', 'file'], 'icon': folder_icon},
			'dir': {'is_dir': True, 'files': ['subdir'], 'icon': folder_icon},
			'dir/subdir': {'is_dir': True, 'icon': folder_icon},
			'file': {'is_dir': False, 'size': 13, 'icon': file_icon}
		}
		self._folder_icon = folder_icon
		self._file_icon = file_icon
		self._fs = MotherFileSystem(StubIconProvider(files))
		self._fs.add_child('null://', NullFileSystem())
		self._register_column(NullColumn())
		stubfs = \
			StubFileSystem(files, default_columns=('core.Name', 'core.Size'))
		self._fs.add_child('stub://', stubfs)
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
	def __init__(self, files):
		self._files = files
	def get_icon(self, url):
		path = splitscheme(url)[1]
		return self._files[path].get('icon', None)