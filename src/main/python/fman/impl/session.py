from base64 import b64encode, b64decode
from fman.impl.util.path import make_absolute
from fman.impl.util.url import get_existing_pardir
from fman.url import as_url, dirname, as_human_readable
from os import getcwd
from os.path import expanduser
from threading import Thread

import logging
import sys

_LOG = logging.getLogger(__name__)

class SessionManager:

	DEFAULT_NUM_PANES = 2
	DEFAULT_COLUMN_WIDTHS = [200, 75]
	_MAIN_WINDOW_VERSION = 1

	def __init__(self, settings, fs, error_handler, fman_version, is_licensed):
		self.is_first_run = not settings
		self._settings = settings
		self._fs = fs
		self._error_handler = error_handler
		self._fman_version = fman_version
		self._is_licensed = is_licensed
	@property
	def was_licensed_on_last_run(self):
		return self._settings.get('is_licensed', False)
	def show_main_window(self, main_window):
		self._restore_window_geometry(main_window)
		pane_infos = self._settings.get('panes', [{}] * self.DEFAULT_NUM_PANES)
		panes = [main_window.add_pane() for _ in range(len(pane_infos))]
		main_window.show_status_message(self._get_startup_message())
		is_first_run = not self._settings
		if is_first_run:
			main_window.showMaximized()
		else:
			# In this case, we assume that _restore_window_geometry restored the
			# window to its previous size/location. We don't want to overwrite
			# these, so call show() instead of showMaximized():
			main_window.show()
		thread_args = (panes, pane_infos, sys.argv[1:])
		Thread(target=self._populate_panes, args=thread_args).start()
	def _restore_window_geometry(self, main_window):
		geometry_b64 = self._settings.get('window_geometry', None)
		if geometry_b64:
			main_window.restoreGeometry(_decode(geometry_b64))
		window_state_b64 = self._settings.get('window_state', None)
		if window_state_b64:
			main_window.restoreState(
				_decode(window_state_b64), self._MAIN_WINDOW_VERSION
			)
	def _get_startup_message(self):
		previous_version = self._settings.get('fman_version', None)
		if not previous_version or previous_version == self._fman_version:
			return 'v%s ready.' % self._fman_version
		return 'Updated to v%s. ' \
			   '<a href="https://fman.io/changelog?s=f">Changelog</a>' \
			   % self._fman_version
	def _populate_panes(self, panes, pane_infos, paths_on_command_line):
		errors = []
		home_dir = expanduser('~')
		for i, (pane_info, pane) in enumerate(zip(pane_infos, panes)):
			try:
				path = make_absolute(paths_on_command_line[i], getcwd())
			except IndexError:
				path = pane_info.get('location', home_dir)
			url = path if '://' in path else as_url(path)
			callback = None
			try:
				if self._fs.is_dir(url):
					location = url
				elif self._fs.exists(url):
					location = dirname(url)
					def callback(pane=pane, url=url):
						pane.place_cursor_at(url)
				else:
					location = get_existing_pardir(url, self._fs.is_dir) \
							   or as_url(home_dir)
				pane.set_location(location, callback)
			except Exception as exc:
				msg = 'Could not load folder %s' % as_human_readable(url)
				errors.append((msg, exc, pane))
			col_widths = pane_info.get('col_widths', self.DEFAULT_COLUMN_WIDTHS)
			pane.set_column_widths(col_widths)
		for msg, exc, pane in errors:
			self._error_handler.report(msg, exc)
			pane.set_location(as_url(home_dir))
	def on_close(self, main_window):
		self._settings['window_geometry'] = _encode(main_window.saveGeometry())
		self._settings['window_state'] = \
			_encode(main_window.saveState(self._MAIN_WINDOW_VERSION))
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
			'location': pane.get_location(),
			'col_widths': pane.get_column_widths()
		}

def _encode(bytes_):
	return b64encode(bytes_).decode('ascii')

def _decode(str_b64):
	return b64decode(str_b64)