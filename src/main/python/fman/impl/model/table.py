from collections import namedtuple
from fman.impl.model.diff import ComputeDiff
from fman.impl.util.qt import DisplayRole, EditRole, DecorationRole, \
	ToolTipRole, ItemIsDropEnabled, ItemIsSelectable, ItemIsEnabled, \
	ItemIsEditable, ItemIsDragEnabled
from PyQt5.QtCore import QModelIndex, QVariant, Qt

class TableModel:
	"""
	Mixin for QAbstractTableModel. Encapsulates the logic for a table where each
	row has an optional icon and the first column is editable, drag enabled and
	potentially drop enabled.
	"""
	def __init__(self, column_headers):
		super().__init__()
		self._column_headers = column_headers
		self._rows = []
	def rowCount(self, parent=QModelIndex()):
		# According to the Qt docs for QAbstractItemModel#rowCount(...):
		#  > When implementing a table based model, rowCount() should
		#  > return 0 when the parent is valid.
		# So in theory, we should check parent.isValid() here. But because this
		# is a 2d-table, `parent` will never be anything but an invalid index.
		# So we forego this check to save ~100ms in performance.
		return len(self._rows)
	def columnCount(self, parent=QModelIndex()):
		# According to the Qt docs for QAbstractItemModel#columnCount(...):
		#  > When implementing a table based model, columnCount() should
		#  > return 0 when the parent is valid.
		# So in theory, we should check parent.isValid() here. But because this
		# is a 2d-table, `parent` will never be anything but an invalid index.
		# So we forego this check to save ~100ms in performance.
		return len(self._column_headers)
	def data(self, index, role=DisplayRole):
		if self._index_is_valid(index):
			if role in (DisplayRole, EditRole):
				return self._rows[index.row()].cells[index.column()].str
			elif role == DecorationRole and index.column() == 0:
				return self._rows[index.row()].icon
			elif role == ToolTipRole:
				return super().data(index, DisplayRole)
		return QVariant()
	def headerData(self, section, orientation, role=DisplayRole):
		if orientation == Qt.Horizontal and role == DisplayRole \
			and 0 <= section < self.columnCount():
			return QVariant(self._column_headers[section])
		return QVariant()
	def flags(self, index):
		if index == QModelIndex():
			# The index representing our current location:
			return ItemIsDropEnabled
		# Need to set ItemIsEnabled - in particular for the last column - to
		# make keyboard shortcut "End" work. When we press this shortcut in a
		# QTableView, Qt jumps to the last column of the last row. But only if
		# this cell is enabled. If it isn't enabled, Qt simply does nothing.
		# So we set the cell to enabled.
		result = ItemIsSelectable | ItemIsEnabled
		if index.column() == 0:
			result |= ItemIsEditable | ItemIsDragEnabled
			if self._rows[index.row()].drop_enabled:
				result |= ItemIsDropEnabled
		return result
	def set_rows(self, rows):
		diff = ComputeDiff(self._rows, rows, key_fn=lambda row: row.key)()
		for entry in diff:
			entry.apply(
				self.insert_rows, self.move_rows, self.update_rows,
				self.remove_rows
			)
	def insert_rows(self, rows, first_rownum=-1):
		if first_rownum == -1:
			first_rownum = len(self._rows)
		self.beginInsertRows(
			QModelIndex(), first_rownum, first_rownum + len(rows) - 1
		)
		self._rows = \
			self._rows[:first_rownum] + rows + self._rows[first_rownum:]
		self.endInsertRows()
	def move_rows(self, cut_start, cut_end, insert_start):
		dst_row = _get_move_destination(cut_start, cut_end, insert_start)
		assert self.beginMoveRows(
			QModelIndex(), cut_start, cut_end - 1, QModelIndex(), dst_row
		)
		rows = self._rows[cut_start:cut_end]
		self._rows = self._rows[:cut_start] + self._rows[cut_end:]
		self._rows = \
			self._rows[:insert_start] + rows + self._rows[insert_start:]
		self.endMoveRows()
	def update_rows(self, rows, first_rownum):
		self._rows[first_rownum : first_rownum + len(rows)] = rows
		top_left = self.index(first_rownum, 0)
		bottom_right = \
			self.index(first_rownum + len(rows) - 1, self.columnCount() - 1)
		self.dataChanged.emit(top_left, bottom_right)
	def remove_rows(self, start, end=-1):
		if end == -1:
			end = start + 1
		self.beginRemoveRows(QModelIndex(), start, end - 1)
		del self._rows[start:end]
		self.endRemoveRows()
	def _index_is_valid(self, index):
		if not index.isValid() or index.model() != self:
			return False
		return 0 <= index.row() < self.rowCount() and \
			   0 <= index.column() < self.columnCount()

def _get_move_destination(cut_start, cut_end, insert_start):
	if cut_start == insert_start:
		raise ValueError('Not a move operation (%d, %d)' % (cut_start, cut_end))
	num_rows = cut_end - cut_start
	return insert_start + (num_rows if cut_start < insert_start else 0)

class Row:
	def __init__(self, key, icon, drop_enabled, cells):
		self.key = key
		self.icon = icon
		self.drop_enabled = drop_enabled
		self.cells = cells
	def __eq__(self, other):
		"""
		Exclude .icon from == comparisons. The reason for this is that
		QFileIconProvider returns objects that don't compare equal even if they
		are equal. This is a problem particularly on Windows. For when we reload
		a directory, QFileIconProvider returns "new" icon values so our
		implementation must assume that all files in the directory have changed
		(when most likely they haven't).

		An earlier implementation used QIcon#cacheKey() in an attempt to solve
		the above problem. In theory, #cacheKey() is precisely meant to help
		with this. But in reality, especially on Windows, the problem remains
		(loading the icon of a file with QFileIconProvider twice gives two QIcon
		instances that look the same but have different cacheKey's).
		"""
		try:
			return (self.key, self.cells, self.drop_enabled) == \
				   (other.key, other.cells, other.drop_enabled)
		except AttributeError:
			return NotImplemented
	def __hash__(self):
		return hash(self.key)
	def __str__(self):
		return '<%s: %s>' % (self.__class__.__name__, self.key)

Cell = namedtuple('Cell', ('str', 'sort_value_asc', 'sort_value_desc'))