from . import clipboard
from fbs_runtime import system
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
	'get_application_command_aliases', 'load_plugin', 'unload_plugin',
	'clipboard',
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

PLATFORM = system.name()

if PLATFORM == 'Windows':
	DATA_DIRECTORY = join(getenv('APPDATA'), 'fman')
elif PLATFORM == 'Mac':
	DATA_DIRECTORY = expanduser('~/Library/Application Support/fman')
elif PLATFORM == 'Linux':
	DATA_DIRECTORY = expanduser('~/.config/fman')

class ApplicationCommand:
	def __init__(self, window):
		self.window = window
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
		return set(self._commands)
	def run_command(self, name, args=None):
		if args is None:
			args = {}
		while True:
			for listener in self._listeners:
				rewritten = listener.on_command(name, args)
				if rewritten:
					name, args = rewritten
					break
			else:
				break
		return self._commands[name](**args)
	def get_command_aliases(self, command_name):
		return self._commands[command_name].get_aliases()
	def is_command_visible(self, command_name):
		return self._commands[command_name].is_visible()
	def _register_command(self, command_name, command):
		self._commands[command_name] = command

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
	def place_cursor_at(self, file_url):
		self._widget.place_cursor_at(file_url)
	# TODO: Rename to get_location()
	def get_path(self):
		return self._widget.get_location()
	# TODO: Rename to set_location(...)
	def set_path(self, dir_url, callback=None):
		self._widget.set_location(dir_url, callback)
	def reload(self):
		self._widget.reload()
	def edit_name(self, file_url, selection_start=0, selection_end=None):
		self._widget.edit_name(file_url, selection_start, selection_end)
	def select_all(self):
		self._widget.select_all()
	def clear_selection(self):
		self._widget.clear_selection()
	def toggle_selection(self, file_url):
		self._widget.toggle_selection(file_url)
	def focus(self):
		self._widget.focus()
	def _has_focus(self):
		return self._widget.hasFocus()

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
	def is_visible(self):
		return True
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
	def on_doubleclicked(self, file_url):
		pass
	def on_name_edited(self, file_url, new_name):
		pass
	# TODO: Rename to on_location_changed()
	def on_path_changed(self):
		pass
	def on_files_dropped(self, file_urls, dest_dir, is_copy_not_move):
		pass
	def on_command(self, command_name, args):
		pass

def load_json(name, default=None, save_on_quit=False):
	return _get_plugin_support().load_json(name, default, save_on_quit)

def save_json(name, value=None):
	return _get_plugin_support().save_json(name, value)

def show_alert(text, buttons=OK, default_button=OK):
	return _get_ui().show_alert(text, buttons, default_button)

def show_prompt(text, default='', selection_start=0, selection_end=None):
	return _get_ui().show_prompt(text, default, selection_start, selection_end)

def show_status_message(text, timeout_secs=None):
	return _get_ui().show_status_message(text, timeout_secs)

def clear_status_message():
	return _get_ui().clear_status_message()

def show_file_open_dialog(caption, dir_path, filter_text=''):
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
	def __repr__(self):
		return '<%s: %s>' % (self.__class__.__name__, self.title)

def get_application_commands():
	return _get_plugin_support().get_application_commands()

def run_application_command(name, args=None):
	if args is None:
		args = {}
	return _get_plugin_support().run_application_command(name, args)

def get_application_command_aliases(command_name):
	return _get_plugin_support().get_application_command_aliases(command_name)

def load_plugin(plugin_path):
	return _get_plugin_support().load_plugin(plugin_path)

def unload_plugin(plugin_path):
	"""
	Raises ValueError if the plugin was not loaded.
	"""
	_get_plugin_support().unload_plugin(plugin_path)

def _get_plugin_support():
	return _get_app_ctxt().plugin_support

def _get_ui():
	return _get_app_ctxt().main_window

def _get_app_ctxt():
	from fman.impl.application_context import get_application_context
	return get_application_context()