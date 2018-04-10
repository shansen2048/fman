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

	_NUM_FILES = 100
	_NUM_VISIBLE_ROWS = 10

	def test_location_after_init(self):
		self.assertEqual('null://', self._model.get_location())
		self.assertEqual((self._null_column,), self._model.get_columns())
	def test_set_location(self):
		inited = Event()
		self._model.set_location('stub://', callback=inited.set)
		self.assertEqual('stub://', self._model.get_location())
		inited.wait(self._timeout)
		self._expect_column_headers(['Name', 'Size'])
		self.assertEqual(
			(self._name_column, self._size_column), self._model.get_columns()
		)
		# Should load at least the first column:
		first_column = [row[0] for row in self._get_data()]
		self.assertEqual(
			['dir'] + [str(i) for i in range(self._NUM_FILES)], first_column
		)
		self.assertTrue(self._model.sourceModel().sort_col_is_loaded(0, True))
		self._load_visible_rows()
		rows = self._get_data()[:self._NUM_VISIBLE_ROWS]
		icons = self._get_data(DecorationRole)[:self._NUM_VISIBLE_ROWS]
		self.assertEqual(('dir', ''), rows[0])
		self.assertEqual((self._folder_icon, None), icons[0])
		self.assertEqual(
			[
				(str(i), '%d B' % self._files[str(i)]['size'])
				for i in range(self._NUM_VISIBLE_ROWS - 1)
			],
			rows[1:]
		)
		self.assertEqual(
			[(self._file_icon, None)] * (self._NUM_VISIBLE_ROWS - 1), icons[1:]
		)
	def _load_visible_rows(self):
		loaded = Event()
		load_rows = run_in_main_thread(self._model.load_rows)
		load_rows(range(self._NUM_VISIBLE_ROWS), callback=loaded.set)
		loaded.wait(self._timeout)
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
		self.test_set_location()
		self._set_location('stub://dir')
		self._files['0']['size'] = 87
		self._set_location('stub://')
		self._load_visible_rows()
		end_time = time() + (self._timeout or sys.float_info.max)
		while time() < end_time:
			if self._get_data()[:2] == [('dir', ''), ('0', '87 B')]:
				break
			sleep(.1)
		else:
			self.fail("Model failed to reload.")
	def test_sort(self):
		self.test_set_location()
		sorted_ = Event()
		connect_once(self._model.sort_order_changed, lambda *_: sorted_.set())
		run_in_main_thread(self._model.sort)(1)
		sorted_.wait(self._timeout)
		expected_files_sort_order = ['dir'] + sorted(
			(str(i) for i in range(self._NUM_FILES)),
			key=lambda fname: self._files[fname]['size']
		)
		first_column = [row[0] for row in self._get_data()]
		self.assertEqual(expected_files_sort_order, first_column)
		self._load_visible_rows()
		self.assertEqual(
			[
				(fname, '%s B' % self._files[fname]['size'])
				for fname in expected_files_sort_order[1:self._NUM_VISIBLE_ROWS]
			],
			self._get_data()[1:self._NUM_VISIBLE_ROWS]
		)
	def _set_location(self, location):
		loaded = Event()
		self._model.set_location(location, callback=loaded.set)
		loaded.wait(self._timeout)
	def _get_data(self, role=DisplayRole):
		result = []
		for row in range(self._model.rowCount()):
			result.append(tuple(
				self._model.data(self._index(row, col), role)
				for col in range(self._model.columnCount())
			))
		return result
	def _index(self, row, column=0):
		return self._model.index(row, column)
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
			'': {'is_dir': True, 'files': ['dir'], 'icon': folder_icon},
			'dir': {'is_dir': True, 'files': ['subdir'], 'icon': folder_icon},
			'dir/subdir': {'is_dir': True, 'icon': folder_icon}
		}
		for i in range(self._NUM_FILES):
			fname = str(i)
			# Make size ordering different from ordering by name:
			size = i + (0 if i % 2 else self._NUM_FILES)
			self._files[fname] = {
				'is_dir': False, 'size': size, 'icon': file_icon
			}
			self._files['']['files'].append(fname)
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