from base64 import b64encode, b64decode
from fman.util import system
from os import makedirs, getcwd
from os.path import expanduser, dirname, realpath, normpath, splitdrive

import json
import sys

class SessionManager:

	DEFAULT_NUM_PANES = 2
	DEFAULT_COLUMN_WIDTHS = [200, 75]
	DEFAULT_WINDOW_SIZE = (800, 450)

	def __init__(self, json_path, fman_version):
		self.json_path = json_path
		self.fman_version = fman_version
		self._json_dict = None
	def on_startup(self, main_window):
		try:
			with open(self.json_path, 'r') as f:
				self._json_dict = json.load(f)
		except FileNotFoundError:
			self._json_dict = {}
		self._restore_panes(main_window, sys.argv[1:])
		self._restore_window_geometry(main_window)
		main_window.show_status_message(self._get_startup_message())
	def _restore_panes(self, main_window, paths_on_command_line):
		panes = self._json_dict.get('panes', [{}] * self.DEFAULT_NUM_PANES)
		for i, pane_info in enumerate(panes):
			pane = main_window.add_pane()
			try:
				path = self._make_absolute(paths_on_command_line[i], getcwd())
			except IndexError:
				path = pane_info.get('location', expanduser('~'))
			pane.set_path(path)
			col_widths = pane_info.get('col_widths', self.DEFAULT_COLUMN_WIDTHS)
			pane.set_column_widths(col_widths)
	def _make_absolute(self, path, cwd):
		if normpath(path) == '.':
			return cwd
		if system.is_windows() and path == splitdrive(path)[0]:
			# Add trailing backslash for drives, eg. "C:"
			return path + ('' if path.endswith('\\') else '\\')
		return realpath(expanduser(path))
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
		previous_version = self._json_dict.get('fman_version', '')
		if not previous_version or previous_version == self.fman_version:
			return 'v%s ready.' % self.fman_version
		return 'Updated to v%s. ' \
			   '<a href="https://fman.io/changelog">Changelog</a>' \
			   % self.fman_version
	def on_close(self, main_window):
		self._json_dict['window_geometry'] = _encode(main_window.saveGeometry())
		self._json_dict['window_state'] = _encode(main_window.saveState())
		self._json_dict['panes'] = \
			list(map(self._read_settings_from_pane, main_window.get_panes()))
		self._json_dict['fman_version'] = self.fman_version
		makedirs(dirname(self.json_path), exist_ok=True)
		with open(self.json_path, 'w') as f:
			json.dump(self._json_dict, f)
	def _read_settings_from_pane(self, pane):
		return {
			'location': pane.get_path(),
			'col_widths': pane.get_column_widths()
		}

def _encode(bytes_):
	return b64encode(bytes_).decode('ascii')

def _decode(str_b64):
	return b64decode(str_b64)