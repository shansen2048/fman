from fman.util.system import is_mac, is_linux, is_windows
from PyQt5.QtWidgets import QMessageBox

__all__ = [
	'DirectoryPaneCommand', 'DirectoryPaneListener', 'load_json', 'write_json',
	'PLATFORM', 'YES', 'NO', 'YES_TO_ALL', 'NO_TO_ALL', 'ABORT', 'OK', 'CANCEL'
]

YES = QMessageBox.Yes
NO = QMessageBox.No
YES_TO_ALL = QMessageBox.YesToAll
NO_TO_ALL = QMessageBox.NoToAll
ABORT = QMessageBox.Abort
OK = QMessageBox.Ok
CANCEL = QMessageBox.Cancel

if is_windows():
	PLATFORM = 'Windows'
elif is_mac():
	PLATFORM = 'Mac'
elif is_linux():
	PLATFORM = 'Linux'

class DirectoryPaneCommand:
	def __init__(self, pane):
		self.pane = pane
	def __call__(self, *args, **kwargs):
		raise NotImplementedError()
	def get_chosen_files(self):
		return self.pane.get_selected_files() or \
			   [self.pane.get_file_under_cursor()]

class DirectoryPaneListener:
	def __init__(self, pane):
		self.pane = pane
	def on_doubleclicked(self, file_path):
		pass
	def on_name_edited(self, file_path, new_name):
		pass
	def on_path_changed(self):
		pass

def load_json(name, default=None):
	return _get_plugin_support().load_json(name, default)

def write_json(value, name):
	return _get_plugin_support().write_json(value, name)

def show_alert(text, buttons=OK, default_button=OK):
	return _get_ui().show_alert(text, buttons, default_button)

def show_prompt(text, default=''):
	return _get_ui().show_prompt(text, default)

def show_status_message(text):
	return _get_ui().show_status_message(text)

def show_file_open_dialog(caption, dir_path, filter_text):
	return _get_ui().show_file_open_dialog(caption, dir_path, filter_text)

def show_quicksearch(get_suggestions, get_tab_completion):
	return _get_ui().show_quicksearch(get_suggestions, get_tab_completion)

def _get_plugin_support():
	return _get_app_ctxt().plugin_support

def _get_ui():
	return _get_app_ctxt().main_window

def _get_app_ctxt():
	from fman.impl.application_context import get_application_context
	return get_application_context()