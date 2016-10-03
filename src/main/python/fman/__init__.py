from fman.util.system import is_mac, is_linux, is_windows
from PyQt5.QtWidgets import QMessageBox

__all__ = [
	'DirectoryPaneCommand', 'platform', 'load_json', 'write_json',
	'YES', 'NO', 'YES_TO_ALL', 'NO_TO_ALL', 'ABORT', 'OK', 'CANCEL'
]

YES = QMessageBox.Yes
NO = QMessageBox.No
YES_TO_ALL = QMessageBox.YesToAll
NO_TO_ALL = QMessageBox.NoToAll
ABORT = QMessageBox.Abort
OK = QMessageBox.Ok
CANCEL = QMessageBox.Cancel

def platform():
	if is_windows():
		return 'Windows'
	if is_mac():
		return 'Mac'
	if is_linux():
		return 'Linux'
	raise ValueError('Unknown operating system.')

class DirectoryPaneCommand:
	def __init__(self, pane):
		self.pane = pane
	def __call__(self, *args, **kwargs):
		raise NotImplementedError()
	def get_chosen_files(self):
		return self.pane.get_selected_files() or \
			   [self.pane.get_file_under_cursor()]

def load_json(name):
	return _get_plugin_support().load_json(name)

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

def _get_plugin_support():
	return _get_app_ctxt().plugin_support

def _get_ui():
	return _get_app_ctxt().main_window

def _get_app_ctxt():
	from fman.impl.application_context import get_application_context
	return get_application_context()