from fman.impl.model.drag_and_drop import DragAndDrop
from fman.impl.model.file_watcher import FileWatcher
from fman.impl.model.sorted_table import SortFilterTableModel
from fman.impl.model.table import Cell, Row
from fman.impl.model.worker import Worker
from fman.impl.util.qt import EditRole, connect_once
from fman.impl.util.qt.thread import run_in_main_thread, is_in_main_thread
from fman.url import join, dirname
from functools import wraps
from PyQt5.QtCore import QModelIndex, pyqtSignal, Qt
from PyQt5.QtGui import QIcon, QPixmap

def asynch(priority):
	def decorator(f):
		@wraps(f)
		def result(self, *args, **kwargs):
			if not self._shutdown:
				self._worker.submit(priority, f, self, *args, **kwargs)
		return result
	return decorator

class BaseModel(SortFilterTableModel, DragAndDrop):

	location_loaded = pyqtSignal(str)
	file_renamed = pyqtSignal(str, str)

	def __init__(self, fs, location, columns, sort_column=0, ascending=True):
		column_headers = [column.display_name for column in columns]
		super().__init__(column_headers, sort_column, ascending)
		self._fs = fs
		self._location = location
		self._columns = columns
		self._files = {}
		self._file_watcher = FileWatcher(fs, self)
		self._worker = Worker()
		self._shutdown = False
	def start(self, callback):
		connect_once(self.location_loaded, lambda _: self._file_watcher.start())
		self._worker.start()
		self._init(self._sort_column, self._sort_ascending, callback)
	@asynch(priority=1)
	def _init(self, sort_column, ascending, callback):
		files = []
		file_names = iter(self._fs.iterdir(self._location))
		while not self._shutdown:
			try:
				file_name = next(file_names)
			except (StopIteration, OSError):
				break
			else:
				url = join(self._location, file_name)
				try:
					file_ = self._init_file(url, sort_column, ascending)
				except OSError:
					continue
				files.append(file_)
		else:
			assert self._shutdown
			return
		if files:
			self._set_files(files, sort_column, ascending)
		# Invoke the callback before emitting location_loaded. The reason is
		# that the default location_loaded handler places the cursor - if is has
		# not been placed yet. If the callback does place it, ugly "flickering"
		# effects happen because first the callback and then location_loaded
		# change the cursor position.
		callback()
		self.location_loaded.emit(self._location)
	def _init_file(self, url, sort_column, ascending):
		cells = []
		for i, column in enumerate(self._columns):
			# Load the first column because it is used as an "anchor" when the
			# user types in arbitrary characters:
			str_ = column.get_str(url) if i == 0 else ''
			# Load the current sort value:
			sort_val_asc = sort_val_desc = _NOT_LOADED
			if i == sort_column:
				sort_value = column.get_sort_value(url, ascending)
				if ascending:
					sort_val_asc = sort_value
				else:
					sort_val_desc = sort_value
			cells.append(Cell(str_, sort_val_asc, sort_val_desc))
		return File(url, _get_empty_icon(), False, cells, False)
	@run_in_main_thread
	def _set_files(self, rows, sort_column, ascending):
		self._files = {
			row.url: row for row in rows
		}
		self._sort_column = sort_column
		self._sort_ascending = ascending
		self.update()
	def row_is_loaded(self, rownum):
		return self._rows[rownum].is_loaded
	def load_rows(self, rownums, callback=None):
		assert is_in_main_thread()
		urls = [self._rows[i].url for i in rownums]
		self._load_files_async(urls, callback)
	@asynch(priority=2)
	def _load_files_async(self, urls, callback=None):
		self._load_files(urls, callback)
	def _load_files(self, urls, callback=None):
		files = []
		disappeared = []
		for url in urls:
			if self._shutdown:
				return
			try:
				files.append(self._load_file(url))
			except FileNotFoundError:
				disappeared.append(url)
		self._record_files(files, disappeared)
		if callback is not None:
			callback()
	def _load_file(self, url):
		try:
			is_dir = self._fs.is_dir(url)
		except OSError:
			is_dir = False
		icon = self._fs.icon(url) or _get_empty_icon()
		return File(
			url, icon, is_dir,
			[
				Cell(
					column.get_str(url),
					# TODO: Don't load sort values.
					column.get_sort_value(url, True),
					column.get_sort_value(url, False)
				)
				for column in self._columns
			],
			True
		)
	@run_in_main_thread
	def _record_files(self, files, disappeared=None):
		"""
		Tells the model that the given `files` exist and the URLs given in
		`disappeared` do not exist.
		"""
		if disappeared is None:
			disappeared = []
		for url in disappeared:
			try:
				del self._files[url]
			except KeyError:
				pass
		for file_ in files:
			self._files[file_.url] = file_
		self.update()
	def sort_col_is_loaded(self, column, ascending):
		return all(
			self.get_sort_value(row, column, ascending) != _NOT_LOADED
			for row in self._rows
		)
	@asynch(priority=3)
	def load_sort_col(self, column_index, ascending, callback):
		column = self._columns[column_index]
		loaded = {}
		while True:
			to_load = self._on_sort_col_loaded(column_index, ascending, loaded)
			if not to_load:
				break
			for url in to_load:
				if self._shutdown:
					return
				loaded[url] = column.get_sort_value(url, ascending)
		callback()
	@run_in_main_thread
	def _on_sort_col_loaded(self, column_index, ascending, values):
		missing = [row.url for row in self._rows if row.url not in values]
		if missing:
			return missing
		files_new = []
		for row in self._rows:
			cells = []
			for i, column in enumerate(row.cells):
				if i == column_index:
					if ascending:
						col_val_asc = values[row.url]
						col_val_desc = column.sort_value_desc
					else:
						col_val_asc = column.sort_value_asc
						col_val_desc = values[row.url]
				else:
					col_val_asc = column.sort_value_asc
					col_val_desc = column.sort_value_desc
				cells.append(Cell(column.str, col_val_asc, col_val_desc))
			files_new.append(File(
				row.url, row.icon, row.is_dir, cells, row.is_loaded
			))
		self._record_files(files_new)
	@asynch(priority=4)
	def reload(self):
		f = lambda: (dict(self._files), self._sort_column, self._sort_ascending)
		files_before, sort_column, ascending = run_in_main_thread(f)()
		self._fs.clear_cache(self._location)
		files = []
		file_names = iter(self._fs.iterdir(self._location))
		while not self._shutdown:
			try:
				file_name = next(file_names)
			except (StopIteration, OSError):
				break
			else:
				url = join(self._location, file_name)
				try:
					try:
						file_before = files_before[url]
					except KeyError:
						file_ = self._init_file(url, sort_column, ascending)
					else:
						if file_before.is_loaded:
							file_ = self._load_file(url)
						else:
							file_ = self._init_file(url, sort_column, ascending)
				except FileNotFoundError:
					continue
				files.append(file_)
		else:
			assert self._shutdown
			return
		self._set_files(files, sort_column, ascending)
	def get_columns(self):
		return self._columns
	def get_location(self):
		return self._location
	def url(self, index):
		if not self._index_is_valid(index):
			raise ValueError("Invalid index")
		return self._rows[index.row()].url
	def find(self, url):
		for rownum, row in enumerate(self._rows):
			if row.url == url:
				break
		else:
			raise ValueError('%r is not in list' % url)
		return self.index(rownum, 0)
	def get_rows(self):
		return self._files.values()
	def get_sort_value(self, row, column, ascending):
		cell = row.cells[column]
		result = cell.sort_value_asc if ascending else cell.sort_value_desc
		if result is _NOT_LOADED:
			raise RuntimeError('Sort value is not loaded')
		return result
	def setData(self, index, value, role):
		if role == EditRole:
			self.file_renamed.emit(self.url(index), value)
			return True
		return super().setData(index, value, role)
	@asynch(priority=5)
	def notify_file_added(self, url):
		assert dirname(url) == self._location
		self._load_files([url])
	@asynch(priority=5)
	def notify_file_changed(self, url):
		assert dirname(url) == self._location
		self._fs.clear_cache(url)
		self._load_files([url])
	@asynch(priority=5)
	def notify_file_renamed(self, old_url, new_url):
		assert dirname(old_url) == dirname(new_url) == self._location
		self._fs.clear_cache(old_url)
		self._load_files([old_url, new_url])
	@asynch(priority=5)
	def notify_file_removed(self, url):
		assert dirname(url) == self._location
		self._fs.clear_cache(url)
		self._load_files([url])
	def shutdown(self):
		self._shutdown = True
		self._file_watcher.shutdown()
		self._worker.shutdown()

_NOT_LOADED = object()

class File(Row):
	def __init__(self, url, icon, is_dir, cells, is_loaded):
		super().__init__(url, icon, is_dir, cells)
		self.is_loaded = is_loaded
	@property
	def url(self):
		return self.key
	@property
	def is_dir(self):
		return self.drop_enabled

@run_in_main_thread
def _get_empty_icon(size=128):
	"""
	It would be tempting to simply use `None` as an "empty" icon. But when we do
	this, Qt does not reserve the space usually taken up by the icon. (It's like
	display:none vs visibility:hidden in CSS.) This leads to ugly shifting
	effects as rows are loaded and the "empty" icon is replaced by a real one.
	To avoid this, our "empty" icon is in fact a transparent placeholder.

	The reason why this is a getter instead of a global variable is that we
	can't instantiate QPixmap at the module level. This is because QPixmap(...)
	requires a QApplication, which has not yet been instantiated at import time.
	"""
	global _empty_icon
	if _empty_icon is None:
		pixmap = QPixmap(size, size)
		pixmap.fill(Qt.transparent)
		_empty_icon = QIcon(pixmap)
	return _empty_icon

_empty_icon = None