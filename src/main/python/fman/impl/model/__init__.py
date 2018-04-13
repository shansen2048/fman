from fman.impl.model.base import BaseModel
from fman.impl.model.drag_and_drop import DragAndDrop
from fman.impl.model.diff import ComputeDiff
from fman.impl.model.file_watcher import FileWatcher
from fman.impl.model.table import TableModel, Cell, Row
from fman.impl.util.qt.thread import run_in_main_thread
from fman.impl.util.url import get_existing_pardir, is_pardir
from PyQt5.QtCore import pyqtSignal, QSortFilterProxyModel, Qt

class SortedFileSystemModel(QSortFilterProxyModel):

	location_changed = pyqtSignal(str)
	location_loaded = pyqtSignal(str)
	file_renamed = pyqtSignal(str, str)
	files_dropped = pyqtSignal(list, str, bool)
	sort_order_changed = pyqtSignal(int, int)

	def __init__(self, parent, fs, null_location):
		super().__init__(parent)
		self._fs = fs
		self._null_location = null_location
		self._filters = []
		self._already_visited = set()
		self.set_location(null_location)
		self._fs.file_removed.add_callback(self._on_file_removed)
	def set_location(self, url, sort_column='', ascending=True, callback=None):
		if callback is None:
			callback = lambda: None
		url = self._fs.resolve(url)
		columns = self._fs.get_columns(url)
		if sort_column:
			column_names = [col.get_qualified_name() for col in columns]
			sort_col_index = column_names.index(sort_column)
		else:
			sort_col_index = 0
		old_model = self.sourceModel()
		if old_model:
			if url == old_model.get_location():
				callback()
				return
			old_model.shutdown()
		if url in self._already_visited:
			orig_callback = callback
			def callback():
				orig_callback()
				self.reload()
		self._set_location(url, columns, sort_col_index, ascending, callback)
	@run_in_main_thread
	def _set_location(self, url, columns, sort_col_index, ascending, callback):
		old_model = self.sourceModel()
		if old_model:
			self._disconnect_signals(old_model)
		new_model = BaseModel(self._fs, url, columns, sort_col_index, ascending)
		for filter_ in self._filters:
			new_model.add_filter(filter_)
		self.setSourceModel(new_model)
		self._connect_signals(new_model)
		new_model.start(callback)
		self._already_visited.add(url)
		self.location_changed.emit(url)
	def row_is_loaded(self, i):
		source_row = self.mapToSource(self.index(i, 0)).row()
		return self.sourceModel().row_is_loaded(source_row)
	def load_rows(self, rows, callback=None):
		source_rows = [self._map_row_to_source(row) for row in rows]
		self.sourceModel().load_rows(source_rows, callback)
	def _map_row_to_source(self, i):
		return self.mapToSource(self.index(i, 0)).row()
	def get_location(self):
		return self.sourceModel().get_location()
	def get_columns(self):
		return self.sourceModel().get_columns()
	def reload(self):
		self.sourceModel().reload()
	def sort(self, column, order=Qt.AscendingOrder):
		self.sourceModel().sort(column, order)
	def add_filter(self, filter_):
		self.sourceModel().add_filter(filter_)
		self._filters.append(filter_)
	def invalidate_filters(self):
		self.sourceModel().update()
	def url(self, index):
		return self.sourceModel().url(self.mapToSource(index))
	def find(self, url):
		return self.mapFromSource(self.sourceModel().find(url))
	def _on_file_removed(self, url):
		if is_pardir(url, self.get_location()):
			existing_pardir = get_existing_pardir(url, self._fs.is_dir)
			self.set_location(existing_pardir or self._null_location)
	def _connect_signals(self, model):
		# Would prefer signal.connect(self.signal.emit) here. But PyQt doesn't
		# support it. So we need Python wrappers "_emit_...":
		model.location_loaded.connect(self._emit_location_loaded)
		model.file_renamed.connect(self._emit_file_renamed)
		model.files_dropped.connect(self._emit_files_dropped)
		model.sort_order_changed.connect(self._emit_sort_order_changed)
	def _disconnect_signals(self, model):
		# Would prefer signal.disconnect(self.signal.emit) here. But PyQt
		# doesn't support it. So we need Python wrappers "_emit_...":
		model.location_loaded.disconnect(self._emit_location_loaded)
		model.file_renamed.disconnect(self._emit_file_renamed)
		model.files_dropped.disconnect(self._emit_files_dropped)
		model.sort_order_changed.disconnect(self._emit_sort_order_changed)
	def _emit_location_loaded(self, location):
		self.location_loaded.emit(location)
	def _emit_file_renamed(self, old, new):
		self.file_renamed.emit(old, new)
	def _emit_files_dropped(self, urls, dest, is_copy):
		self.files_dropped.emit(urls, dest, is_copy)
	def _emit_sort_order_changed(self, column, order):
		self.sort_order_changed.emit(column, order)
	def __str__(self):
		return '<%s: %s>' % (self.__class__.__name__, self._location)