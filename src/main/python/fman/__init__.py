from fman.util.system import is_mac, is_linux, is_windows
from os import getenv
from os.path import join, expanduser
from PyQt5.QtWidgets import QMessageBox

__all__ = [
	'ApplicationCommand', 'DirectoryPaneCommand', 'DirectoryPaneListener',
	'load_json', 'save_json',
	'show_alert', 'show_prompt', 'show_status_message', 'clear_status_message',
	'show_file_open_dialog',
	'show_quicksearch', 'QuicksearchItem',
	'get_application_commands', 'run_application_command',
	'PLATFORM', 'FMAN_VERSION', 'DATA_DIRECTORY',
	'OK', 'CANCEL', 'YES', 'NO', 'YES_TO_ALL', 'NO_TO_ALL', 'ABORT'
]

YES = QMessageBox.Yes
NO = QMessageBox.No
YES_TO_ALL = QMessageBox.YesToAll
NO_TO_ALL = QMessageBox.NoToAll
ABORT = QMessageBox.Abort
OK = QMessageBox.Ok
CANCEL = QMessageBox.Cancel

FMAN_VERSION = ''

if is_windows():
	PLATFORM = 'Windows'
	DATA_DIRECTORY = join(getenv('APPDATA'), 'fman')
elif is_mac():
	PLATFORM = 'Mac'
	DATA_DIRECTORY = expanduser('~/Library/Application Support/fman')
elif is_linux():
	PLATFORM = 'Linux'
	DATA_DIRECTORY = expanduser('~/.config/fman')

class ApplicationCommand:
	def __call__(self, *args, **kwargs):
		raise NotImplementedError()

class DirectoryPane:
	def __init__(self, window, widget):
		self.window = window
		self._widget = widget
		self._commands = {}
		self._listeners = []

	def _add_listener(self, listener):
		self._listeners.append(listener)
	def _broadcast(self, event, *args):
		for listener in self._listeners:
			getattr(listener, event)(*args)

	def get_commands(self):
		return self._commands
	def run_command(self, name, args=None):
		if args is None:
			args = {}
		return self._commands[name](**args)
	def _register_command(self, command_name, command):
		self._commands[command_name] = command

	@property
	def id(self):
		# TODO: Remove this migration after April, 2017.
		raise AttributeError(
			"DirectoryPane#id was removed from fman's API. Please update your "
			"plugins."
		)
	def _add_filter(self, filter_):
		self._widget.add_filter(filter_)
	def _invalidate_filters(self):
		self._widget.invalidate_filters()

	def get_selected_files(self):
		return self._widget.get_selected_files()
	def get_file_under_cursor(self):
		return self._widget.get_file_under_cursor()
	def move_cursor_down(self, toggle_selection=False):
		self._widget.move_cursor_down(toggle_selection)
	def move_cursor_up(self, toggle_selection=False):
		self._widget.move_cursor_up(toggle_selection)
	def move_cursor_home(self, toggle_selection=False):
		self._widget.move_cursor_home(toggle_selection)
	def move_cursor_end(self, toggle_selection=False):
		self._widget.move_cursor_end(toggle_selection)
	def move_cursor_page_down(self, toggle_selection=False):
		self._widget.move_cursor_page_down(toggle_selection)
	def move_cursor_page_up(self, toggle_selection=False):
		self._widget.move_cursor_page_up(toggle_selection)
	def place_cursor_at(self, file_path):
		self._widget.place_cursor_at(file_path)
	def get_path(self):
		return self._widget.get_path()
	def set_path(self, dir_path, callback=None):
		self._widget.set_path(dir_path, callback)
	def edit_name(self, file_path):
		self._widget.edit_name(file_path)
	def select_all(self):
		self._widget.select_all()
	def clear_selection(self):
		self._widget.clear_selection()
	def toggle_selection(self, file_path):
		self._widget.toggle_selection(file_path)
	def focus(self):
		self._widget.focus()

class Window:
	def __init__(self):
		self._panes = []
	def get_panes(self):
		return self._panes
	def add_pane(self, pane_widget):
		result = DirectoryPane(self, pane_widget)
		self._panes.append(result)
		return result

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
	def on_files_dropped(self, file_paths, dest_dir, is_copy_not_move):
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

def show_quicksearch(get_items, get_tab_completion=None):
	return _get_ui().show_quicksearch(get_items, get_tab_completion)

class QuicksearchItem:
	def __init__(
		self, value, title=None, highlight=None, hint='', description=''
	):
		if title is None:
			title = value
		if highlight is None:
			highlight = []
		self.value = value
		self.title = title
		self.highlight = highlight
		self.hint = hint
		self.description = description

def get_application_commands():
	return _get_plugin_support().get_application_commands()

def run_application_command(name, args=None):
	if args is None:
		args = {}
	return _get_plugin_support().run_application_command(name, args)

def _get_plugin_support():
	return _get_app_ctxt().plugin_support

def _get_ui():
	return _get_app_ctxt().main_window

def _get_app_ctxt():
	from fman.impl.application_context import get_application_context
	return get_application_context()