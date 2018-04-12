from fman.impl.model.table import TableModel
from PyQt5.QtCore import Qt, pyqtSignal

class SortedTableModel(TableModel):

	sort_order_changed = pyqtSignal(int, int)

	def __init__(self, column_headers, sort_column=0, ascending=True):
		super().__init__(column_headers)
		self._sort_column = sort_column
		self._sort_ascending = ascending
	def get_sort_value(self, row, column, ascending):
		raise NotImplementedError()
	def set_rows(self, rows):
		super().set_rows(self._sorted(rows))
	def sort(self, column, order=Qt.AscendingOrder):
		ascending = order == Qt. AscendingOrder
		if (column, ascending) == (self._sort_column, self._sort_ascending):
			return
		self.layoutAboutToBeChanged.emit([], self.VerticalSortHint)
		self._sort_column = column
		self._sort_ascending = ascending
		new_rows = self._sorted(self._rows)
		for index in self.persistentIndexList():
			old_row = self._rows[index.row()]
			for i, row in enumerate(new_rows):
				if row.key == old_row.key:
					self.changePersistentIndex(
						index, self.index(i, index.column())
					)
					break
		self._rows = new_rows
		self.layoutChanged.emit([], self.VerticalSortHint)
		self.sort_order_changed.emit(column, order)
	def _sorted(self, rows):
		return sorted(
			rows, key=self._sort_key, reverse=not self._sort_ascending
		)
	def _sort_key(self, row):
		return self.get_sort_value(row, self._sort_column, self._sort_ascending)