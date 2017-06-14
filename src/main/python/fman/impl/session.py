from base64 import b64encode, b64decode
from fman.util import system
from json import JSONDecodeError
from os import makedirs, getcwd
from os.path import expanduser, dirname, realpath, normpath, splitdrive

import json
import sys

class SessionManager:

	DEFAULT_NUM_PANES = 2
	DEFAULT_COLUMN_WIDTHS = [200, 75]

	def __init__(self, json_path, fman_version, is_licensed):
		self._json_path = json_path
		self._fman_version = fman_version
		self._is_licensed = is_licensed
		self.is_first_run = False
		try:
			with open(self._json_path, 'r') as f:
				self._json_dict = json.load(f)
		except FileNotFoundError:
			self._json_dict = {}
			self.is_first_run = True
		except JSONDecodeError:
			self._json_dict = {
				'fman_version': self._fman_version
			}
	@property
	def previous_fman_version(self):
		return self._json_dict.get('fman_version', None)
	@property
	def was_licensed_on_last_run(self):
		return self._json_dict.get('is_licensed', None)
	def show_main_window(self, main_window):
		self._restore_panes(main_window, sys.argv[1:])
		self._restore_window_geometry(main_window)
		main_window.show_status_message(self._get_startup_message())
		if self.is_first_run:
			main_window.showMaximized()
		else:
			# In this case, we assume that _restore_window_geometry restored the
			# window to its previous size/location. We don't want to overwrite
			# these, so call show() instead of showMaximized():
			main_window.show()
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
		window_state_b64 = self._json_dict.get('window_state', None)
		if window_state_b64:
			main_window.restoreState(_decode(window_state_b64))
	def _get_startup_message(self):
		previous_version = self.previous_fman_version
		if not previous_version or previous_version == self._fman_version:
			return 'v%s ready.' % self._fman_version
		return 'Updated to v%s. ' \
			   '<a href="https://fman.io/changelog?s=f">Changelog</a>' \
			   % self._fman_version
	def on_close(self, main_window):
		self._json_dict['window_geometry'] = _encode(main_window.saveGeometry())
		self._json_dict['window_state'] = _encode(main_window.saveState())
		self._json_dict['panes'] = \
			list(map(self._read_settings_from_pane, main_window.get_panes()))
		self._json_dict['fman_version'] = self._fman_version
		self._json_dict['is_licensed'] = self._is_licensed
		try:
			makedirs(dirname(self._json_path), exist_ok=True)
			with open(self._json_path, 'w') as f:
				json.dump(self._json_dict, f)
		except OSError:
			pass
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