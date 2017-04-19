from base64 import b64encode, b64decode
from fman import DATA_DIRECTORY
from fman.impl.plugins import SETTINGS_PLUGIN_NAME
from fman.util import system, parse_version
from os import makedirs, getcwd, listdir, rename
from os.path import expanduser, dirname, realpath, normpath, splitdrive, join, \
	isdir

import json
import sys

class SessionManager:

	DEFAULT_NUM_PANES = 2
	DEFAULT_COLUMN_WIDTHS = [200, 75]
	DEFAULT_WINDOW_SIZE = (800, 450)

	def __init__(self, json_path, fman_version):
		self._json_path = json_path
		self._fman_version = fman_version
		try:
			with open(self._json_path, 'r') as f:
				self._json_dict = json.load(f)
		except FileNotFoundError:
			self._json_dict = {}
	@property
	def previous_fman_version(self):
		return self._json_dict.get('fman_version', None)
	def migrate_old_plugin_structure(self):
		previous_version = self.previous_fman_version or self._fman_version
		if parse_version(previous_version) >= (0, 3, 9):
			return
		plugins_directory = join(DATA_DIRECTORY, 'Plugins')
		user_plugin = join(plugins_directory, 'User')
		try:
			user_plugin_contents = listdir(user_plugin)
		except FileNotFoundError:
			return
		if SETTINGS_PLUGIN_NAME in user_plugin_contents:
			# This is not expected. Abort.
			return
		# Move everything from the old User plugin to the new Settings plugin:
		settings_plugin = join(user_plugin, SETTINGS_PLUGIN_NAME)
		makedirs(settings_plugin)
		for file_ in user_plugin_contents:
			rename(join(user_plugin, file_), join(settings_plugin, file_))
		# Migrate other plugins:
		other_plugins = [
			p for p in listdir(plugins_directory)
			if p != 'User' and isdir(join(plugins_directory, p))
		]
		assert 'Third-party' not in other_plugins
		for other_plugin in other_plugins:
			rename(
				join(plugins_directory, other_plugin),
				join(user_plugin, other_plugin)
			)
	def on_startup(self, main_window):
		self._restore_panes(main_window, sys.argv[1:])
		self._restore_window_geometry(main_window)
		main_window.show_status_message(self._get_startup_message())
	def _restore_panes(self, main_window, paths_on_command_line):
		panes = self._json_dict.get('panes', [{}] * self.DEFAULT_NUM_PANES)
		for i, pane_info in enumerate(panes):
			pane = main_window.add_pane()
			try:
				path = _make_absolute(paths_on_command_line[i], getcwd())
			except IndexError:
				path = pane_info.get('location', expanduser('~'))
			pane.set_path(path)
			col_widths = pane_info.get('col_widths', self.DEFAULT_COLUMN_WIDTHS)
			pane.set_column_widths(col_widths)
	def _restore_window_geometry(self, main_window):
		geometry_b64 = self._json_dict.get('window_geometry', None)
		if geometry_b64:
			main_window.restoreGeometry(_decode(geometry_b64))
		else:
			main_window.resize(*self.DEFAULT_WINDOW_SIZE)
		window_state_b64 = self._json_dict.get('window_state', None)
		if window_state_b64:
			main_window.restoreState(_decode(window_state_b64))
	def _get_startup_message(self):
		previous_version = self.previous_fman_version
		if not previous_version or previous_version == self._fman_version:
			return 'v%s ready.' % self._fman_version
		return 'Updated to v%s. ' \
			   '<a href="https://fman.io/changelog">Changelog</a>' \
			   % self._fman_version
	def on_close(self, main_window):
		self._json_dict['window_geometry'] = _encode(main_window.saveGeometry())
		self._json_dict['window_state'] = _encode(main_window.saveState())
		self._json_dict['panes'] = \
			list(map(self._read_settings_from_pane, main_window.get_panes()))
		self._json_dict['fman_version'] = self._fman_version
		makedirs(dirname(self._json_path), exist_ok=True)
		with open(self._json_path, 'w') as f:
			json.dump(self._json_dict, f)
	def _read_settings_from_pane(self, pane):
		return {
			'location': pane.get_path(),
			'col_widths': pane.get_column_widths()
		}

def _make_absolute(path, cwd):
	if normpath(path) == '.':
		return cwd
	if system.is_windows() and path == splitdrive(path)[0]:
		# Add trailing backslash for drives, eg. "C:"
		return path + ('' if path.endswith('\\') else '\\')
	return realpath(expanduser(path))

def _encode(bytes_):
	return b64encode(bytes_).decode('ascii')

def _decode(str_b64):
	return b64decode(str_b64)