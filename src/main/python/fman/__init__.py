from fman.util.system import is_mac, is_linux, is_windows
from os import getenv
from os.path import join, expanduser
from PyQt5.QtWidgets import QMessageBox

__all__ = [
	'DirectoryPaneCommand', 'DirectoryPaneListener', 'load_json', 'save_json',
	'show_alert', 'show_prompt', 'show_status_message', 'clear_status_message',
	'show_file_open_dialog', 'show_quicksearch',
	'PLATFORM', 'DATA_DIRECTORY', 'YES', 'NO', 'YES_TO_ALL', 'NO_TO_ALL',
	'ABORT', 'OK', 'CANCEL'
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
	DATA_DIRECTORY = join(getenv('APPDATA'), 'fman')
elif is_mac():
	PLATFORM = 'Mac'
	DATA_DIRECTORY = expanduser('~/Library/Application Support/fman')
elif is_linux():
	PLATFORM = 'Linux'
	DATA_DIRECTORY = expanduser('~/.config/fman')

class DirectoryPaneCommand:
	def __init__(self, pane):
		self.pane = pane
	def __call__(self, *args, **kwargs):
		raise NotImplementedError()
	def get_chosen_files(self):
		selected_files = self.pane.get_selected_files()
		if selected_files:
			return selected_files
		file_under_cursor = self.pane.get_file_under_cursor()
		if file_under_cursor:
			return [file_under_cursor]
		return []

class DirectoryPaneListener:
	def __init__(self, pane):
		self.pane = pane
	def on_doubleclicked(self, file_path):
		pass
	def on_name_edited(self, file_path, new_name):
		pass
	def on_path_changed(self):
		pass

def load_json(name, default=None, save_on_quit=False):
	return _get_plugin_support().load_json(name, default, save_on_quit)

def save_json(name, value=None):
	return _get_plugin_support().save_json(name, value)

def show_alert(text, buttons=OK, default_button=OK):
	return _get_ui().show_alert(text, buttons, default_button)

def show_prompt(text, default=''):
	return _get_ui().show_prompt(text, default)

def show_status_message(text, timeout_secs=None):
	return _get_ui().show_status_message(text, timeout_secs)

def clear_status_message():
	return _get_ui().clear_status_message()

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