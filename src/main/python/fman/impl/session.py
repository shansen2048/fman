from base64 import b64encode, b64decode
from fman.util import system
from os import getcwd
from os.path import expanduser, realpath, normpath, splitdrive

import sys

class SessionManager:

	DEFAULT_NUM_PANES = 2
	DEFAULT_COLUMN_WIDTHS = [200, 75]

	def __init__(self, settings, fman_version, is_licensed):
		self.is_first_run = not settings
		self._settings = settings
		self._fman_version = fman_version
		self._is_licensed = is_licensed
	@property
	def was_licensed_on_last_run(self):
		return self._settings.get('is_licensed', False)
	def show_main_window(self, main_window):
		self._restore_panes(main_window, sys.argv[1:])
		self._restore_window_geometry(main_window)
		main_window.show_status_message(self._get_startup_message())
		is_first_run = not self._settings
		if is_first_run:
			main_window.showMaximized()
		else:
			# In this case, we assume that _restore_window_geometry restored the
			# window to its previous size/location. We don't want to overwrite
			# these, so call show() instead of showMaximized():
			main_window.show()
	def _restore_panes(self, main_window, paths_on_command_line):
		panes = self._settings.get('panes', [{}] * self.DEFAULT_NUM_PANES)
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
		geometry_b64 = self._settings.get('window_geometry', None)
		if geometry_b64:
			main_window.restoreGeometry(_decode(geometry_b64))
		window_state_b64 = self._settings.get('window_state', None)
		if window_state_b64:
			main_window.restoreState(_decode(window_state_b64))
	def _get_startup_message(self):
		previous_version = self._settings.get('fman_version', None)
		if not previous_version or previous_version == self._fman_version:
			return 'v%s ready.' % self._fman_version
		return 'Updated to v%s. ' \
			   '<a href="https://fman.io/changelog?s=f">Changelog</a>' \
			   % self._fman_version
	def on_close(self, main_window):
		self._settings['window_geometry'] = _encode(main_window.saveGeometry())
		self._settings['window_state'] = _encode(main_window.saveState())
		self._settings['panes'] = \
			list(map(self._read_pane_settings, main_window.get_panes()))
		self._settings['fman_version'] = self._fman_version
		self._settings['is_licensed'] = self._is_licensed
		try:
			self._settings.flush()
		except OSError:
			pass
	def _read_pane_settings(self, pane):
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