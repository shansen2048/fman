from fman.util.system import get_canonical_os_name as platform
from PyQt5.QtWidgets import QMessageBox

YES = QMessageBox.Yes
NO = QMessageBox.No
YES_TO_ALL = QMessageBox.YesToAll
NO_TO_ALL = QMessageBox.NoToAll
ABORT = QMessageBox.Abort
OK = QMessageBox.Ok
CANCEL = QMessageBox.Cancel

class DirectoryPaneCommand:
	def __init__(self, ui, pane, other_pane):
		self.ui = ui
		self.pane = pane
		self.other_pane = other_pane
	def __call__(self, *args, **kwargs):
		raise NotImplementedError()
	def get_selected_files(self):
		return self.pane.get_selected_files() or \
			   [self.pane.get_file_under_cursor()]

def load_json(name):
	return _get_plugin_support().load_json(name)

def write_json(obj, name):
	return _get_plugin_support().write_json(obj, name)

def _get_plugin_support():
	from fman.impl.application_context import get_application_context
	return get_application_context().plugin_support