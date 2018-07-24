from fman.fs import Column
from fman.impl.model import Model, Cell
from fman.impl.model.model import File, _NOT_LOADED
from fman.impl.util.qt.thread import Executor
from fman_unittest.impl.model import StubFileSystem
from PyQt5.QtCore import QObject, pyqtSignal
from unittest import TestCase

class ModelRecordFilesTest(TestCase):
	def test_load_file(self):
		f_not_loaded = f('s://a', [c('')], False)
		self._model._record_files([f_not_loaded])
		self._expect_data([('',)])
		f_loaded = f('s://a', [c('a')])
		self._model._record_files([f_loaded])
		self._expect_data([('a',)])
	def test_remove_file(self):
		self._model._record_files([f('s://a', [c('a')])])
		self._expect_data([('a',)])
		self._model._record_files([], ['s://a'])
		self._expect_data([])
	def test_remove_two_files(self):
		self._model._record_files([
			f('s://a', [c('a', 0)]),
			f('s://b', [c('b', 1)])
		])
		self._expect_data([('a',), ('b',)])
		self._model._record_files([], ['s://a', 's://b'])
		self._expect_data([])
	def test_remove_files_gap(self):
		self._model._record_files([
			f('s://a', [c('a', 0)]),
			f('s://b', [c('b', 1)]),
			f('s://c', [c('c', 2)]),
			f('s://d', [c('d', 3)]),
		])
		self._expect_data([('a',), ('b',), ('c',), ('d',)])
		self._model._record_files([], ['s://b', 's://d'])
		self._expect_data([('a',), ('c',)])
	def test_remove_files_out_of_order(self):
		self._model._record_files([
			f('s://a', [c('a', 0)]),
			f('s://b', [c('b', 1)]),
			f('s://c', [c('c', 2)])
		])
		self._expect_data([('a',), ('b',), ('c',)])
		self._model._record_files([], ['s://c', 's://b'])
		self._expect_data([('a',)])
	def test_complex(self):
		self._model._record_files([
			f('s://a', [c('a', 0)]),
			f('s://b', [c('b', 1)]),
			f('s://d', [c('d', 2)]),
			f('s://e', [c('e', 4)]),
		])
		self._expect_data([('a',), ('b',), ('d',), ('e',)])
		self._model._record_files([
			f('s://c', [c('c', 3)]),
			f('s://a', [c('a', 5)]),
		], ['s://d'])
		self._expect_data([('b',), ('c',), ('e',), ('a',)])
	def setUp(self):
		super().setUp()
		self._app = StubApp()
		self._executor_before = Executor._INSTANCE # Typically None
		Executor._INSTANCE = Executor(self._app)
		self._fs = StubFileSystem({})
		self._model = Model(self._fs, 'null://', [Column()])
	def tearDown(self):
		self._app.aboutToQuit.emit()
		Executor._INSTANCE = self._executor_before
		super().tearDown()
	def _expect_data(self, expected):
		m = self._model
		actual = [
			tuple(m.data(m.index(i, j)) for j in range(m.columnCount()))
			for i in range(m.rowCount())
		]
		self.assertEqual(expected, actual)

def f(url, cells, is_loaded=False, is_dir=False):
	return File(url, None, is_dir, cells, is_loaded)

def c(str_, sort_value_asc=0, sort_value_desc=_NOT_LOADED):
	return Cell(str_, sort_value_asc, sort_value_desc)

class StubApp(QObject):
	aboutToQuit = pyqtSignal()