from fman.impl.util.qt import DisplayRole, EditRole, ToolTipRole, DecorationRole
from PyQt5.QtCore import QAbstractTableModel, QModelIndex, QVariant
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QTableView

class UniformRowHeights(QTableView):
	"""
	Performance improvement.
	"""
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._row_height = None
	def sizeHintForRow(self, row):
		model = self.model()
		if row < 0 or row >= model.rowCount():
			# Mirror super implementation.
			return -1
		return self.get_row_height()
	def get_row_height(self):
		if self._row_height is None:
			self._row_height = max(self._get_cell_heights())
		return self._row_height
	def changeEvent(self, event):
		# This for instance happens when the style sheet changed. It may affect
		# the calculated row height. So invalidate:
		self._row_height = None
		super().changeEvent(event)
	def _get_cell_heights(self, row=0):
		self.ensurePolished()
		option = self.viewOptions()
		model = self.model()
		dummy_model = DummyModel(
			model.rowCount(), model.columnCount(), option.decorationSize
		)
		for column in range(model.columnCount()):
			index = dummy_model.index(row, column)
			delegate = self.itemDelegate(index)
			if delegate:
				yield delegate.sizeHint(option, index).height()

class DummyModel(QAbstractTableModel):
	"""
	The purpose of this model is to let UniformRowHeights "fake" table rows
	without requiring access to the actual data.
	"""
	def __init__(self, num_rows, num_cols, decoration_size):
		super().__init__()
		self._num_rows = num_rows
		self._num_cols = num_cols
		self.decoration_size = decoration_size
	def rowCount(self, parent=QModelIndex()):
		if parent.isValid():
			# According to the Qt docs for QAbstractItemModel#rowCount(...):
			# "When implementing a table based model, rowCount() should
			#  return 0 when the parent is valid."
			return 0
		return self._num_rows
	def columnCount(self, parent=QModelIndex()):
		if parent.isValid():
			# According to the Qt docs for QAbstractItemModel#columnCount(...):
			# "When implementing a table based model, columnCount() should
			#  return 0 when the parent is valid."
			return 0
		return self._num_cols
	def data(self, index, role=DisplayRole):
		if role in (DisplayRole, EditRole, ToolTipRole):
			return QVariant('')
		elif role == DecorationRole:
			return QPixmap(self.decoration_size)
		return QVariant()
