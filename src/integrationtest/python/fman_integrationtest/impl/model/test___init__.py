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
from time import time, sleep

import sys

class SortedFileSystemModelAT: # Instantiated in fman_integrationtest.test_qt
	def test_location_after_init(self):
		self.assertEqual('null://', self._model.get_location())
		self.assertEqual((self._null_column,), self._model.get_columns())
	def test_set_location(self):
		loaded = Event()
		self._model.set_location('stub://', callback=loaded.set)
		self.assertEqual('stub://', self._model.get_location())
		loaded.wait(self._timeout)
		self._expect_column_headers(['Name', 'Size'])
		self.assertEqual(
			(self._name_column, self._size_column), self._model.get_columns()
		)
		self.assertEqual([('dir', ''), ('file', '13 B')], self._get_data())
		self.assertEqual(
			[(self._folder_icon, None), (self._file_icon, None)],
			self._get_data(DecorationRole)
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
	def test_reloads(self):
		self._set_location('stub://')
		self.assertEqual([('dir', ''), ('file', '13 B')], self._get_data())
		self._set_location('stub://dir')
		self._files['file']['size'] = 87
		self._set_location('stub://')
		expected = [('dir', ''), ('file', '87 B')]
		actual = self._get_data()
		end_time = time() + (self._timeout or sys.float_info.max)
		while actual != expected and time() < end_time:
			actual = self._get_data()
			sleep(.1)
		self.assertEqual(expected, actual)
	def _set_location(self, location):
		loaded = Event()
		self._model.set_location(location, callback=loaded.set)
		loaded.wait(self._timeout)
	def _get_data(self, role=DisplayRole):
		model = self._model
		result = []
		for row in range(self._model.rowCount()):
			result.append(tuple(
				model.data(model.index(row, col), role)
				for col in range(self._model.columnCount())
			))
		return result
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
		if not loaded.wait(timeout=self._timeout):
			self.fail(
				'Timeout expired while waiting for location to be loaded.'
			)
	def setUp(self):
		super().setUp()
		# N.B.: Normally we should have QIcon instances here. But they don't
		# seem to work well with ==. So use strings instead:
		folder_icon = '<folder icon>'
		file_icon = '<file icon>'
		self._files = {
			'': {'is_dir': True, 'files': ['dir', 'file'], 'icon': folder_icon},
			'dir': {'is_dir': True, 'files': ['subdir'], 'icon': folder_icon},
			'dir/subdir': {'is_dir': True, 'icon': folder_icon},
			'file': {'is_dir': False, 'size': 13, 'icon': file_icon}
		}
		self._folder_icon = folder_icon
		self._file_icon = file_icon
		self._fs = MotherFileSystem(StubIconProvider(self._files))
		self._fs.add_child('null://', NullFileSystem())
		self._null_column = NullColumn()
		self._register_column(self._null_column)
		stubfs = StubFileSystem(
			self._files, default_columns=('core.Name', 'core.Size')
		)
		self._fs.add_child('stub://', stubfs)
		self._name_column = Name(self._fs)
		self._register_column(self._name_column)
		self._size_column = Size(self._fs)
		self._register_column(self._size_column)
		self._model = self.run_in_app(
			SortedFileSystemModel, None, self._fs, 'null://'
		)
		self._timeout = None if _is_debugger_attached() else .2
	def tearDown(self):
		self._model.sourceModel().shutdown()
		super().tearDown()
	def _register_column(self, instance):
		self._fs.register_column(instance.get_qualified_name(), instance)

def _is_debugger_attached():
	return bool(sys.gettrace())

class StubIconProvider:
	def __init__(self, files):
		self._files = files
	def get_icon(self, url):
		path = splitscheme(url)[1]
		return self._files[path].get('icon', None)