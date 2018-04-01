from PyQt5.QtWidgets import QTableView

class MoveWithoutUpdatingSelection(QTableView):
	def __init__(self, parent=None):
		super().__init__(parent)
		self.setSelectionMode(self.NoSelection)
	def selectAll(self):
		self.setSelectionMode(self.ContiguousSelection)
		super().selectAll()
		self.setSelectionMode(self.NoSelection)