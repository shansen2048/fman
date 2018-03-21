from base64 import b64encode, b64decode
from concurrent.futures import ThreadPoolExecutor
from fman.impl.util import parse_version
from fman.impl.util.path import make_absolute
from fman.impl.util.qt import connect_once
from fman.impl.util.url import get_existing_pardir
from fman.url import as_url, dirname, as_human_readable
from os import getcwd
from os.path import expanduser
from pathlib import Path
from threading import Thread

import concurrent
import logging
import sys

_LOG = logging.getLogger(__name__)

class SessionManager:

	DEFAULT_NUM_PANES = 2
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
		self._show_startup_messages(main_window)
		is_first_run = not self._settings
		if is_first_run:
			main_window.showMaximized()
		else:
			# In this case, we assume that _restore_window_geometry restored the
			# window to its previous size/location. We don't want to overwrite
			# these, so call show() instead of showMaximized():
			main_window.show()
		thread_args = (panes, pane_infos, sys.argv[1:])
		Thread(target=self._init_panes, args=thread_args).start()
	def _restore_window_geometry(self, main_window):
		geometry_b64 = self._settings.get('window_geometry', None)
		if geometry_b64:
			main_window.restoreGeometry(_decode(geometry_b64))
		window_state_b64 = self._settings.get('window_state', None)
		if window_state_b64:
			main_window.restoreState(
				_decode(window_state_b64), self._MAIN_WINDOW_VERSION
			)
	def _show_startup_messages(self, main_window):
		previous_version = self._settings.get('fman_version', None)
		status_message = 'v%s ready.' % self._fman_version
		if previous_version and previous_version != self._fman_version:
			status_message = \
				'Updated to v%s. <a href="https://fman.io/changelog?s=f">' \
				'Changelog</a>' % self._fman_version
		main_window.show_status_message(status_message)
		# TODO: Remove this migration after Jan 2018:
		if previous_version and parse_version(previous_version) < (0, 7, 0):
			def on_main_window_shown():
				main_window.show_alert(
					'Sorry to bother. fman was updated to version %s. This '
					'adds support for Zip archives (yay!). But it also breaks '
					'some plugins. If you use plugins, you may have to '
					'update or remove them. For more information, please see '
					'<a href="https://fman.io/blog/zip-support-in-fman?s=f">'
					'here</a>.' % self._fman_version
				)
			connect_once(main_window.shown, on_main_window_shown)
	def _get_startup_message(self):
		previous_version = self._settings.get('fman_version', None)
		if not previous_version or previous_version == self._fman_version:
			return 'v%s ready.' % self._fman_version
		return 'Updated to v%s. ' \
			   '<a href="https://fman.io/changelog?s=f">Changelog</a>' \
			   % self._fman_version
	def _init_panes(self, panes, pane_infos, paths_on_command_line):
		with ThreadPoolExecutor(max_workers=len(panes)) as executor:
			futures = [
				executor.submit(self._init_pane, *args) for args in
				self._get_pane_args(panes, pane_infos, paths_on_command_line)
			]
			for future in concurrent.futures.as_completed(futures):
				# Re-raise any exceptions:
				future.result()
	def _get_pane_args(self, panes, pane_infos, paths_on_command_line):
		for i, (pane_info, pane) in enumerate(zip(pane_infos, panes)):
			try:
				path = make_absolute(paths_on_command_line[i], getcwd())
			except IndexError:
				# Note that pane_info['location'] may be None if the pane hadn't
				# yet received a location the last time fman was closed. This
				# likely happens when an error occurs during startup.
				# To cope with this, we use the line below instead of
				#     pane_info.get('location', expanduser('~')).
				path = pane_info.get('location') or expanduser('~')
			url = path if '://' in path else as_url(path)
			yield pane, url, pane_info.get('col_widths')
	def _init_pane(self, pane, url, col_widths=None):
		callback = None
		home_dir = as_url(expanduser('~'))
		try:
			def exists_and_is_dir(url_):
				try:
					return self._fs.is_dir(url_)
				except FileNotFoundError:
					return False
			if exists_and_is_dir(url):
				location = url
			elif self._fs.exists(url):
				location = dirname(url)
				def callback(pane=pane, url=url):
					try:
						pane.place_cursor_at(url)
					except ValueError as file_disappeared:
						pass
			else:
				location = get_existing_pardir(url, exists_and_is_dir) \
						   or home_dir
			pane.set_location(location, callback)
		except Exception as exc:
			msg = 'Could not load folder %s' % as_human_readable(url)
			self._error_handler.report(msg, exc)
			try:
				pane.set_location(home_dir)
			except FileNotFoundError:
				# This can happen for two reasons:
				#  1) The file:// system isn't loaded.
				#  2) The home directory doesn't exist.
				# Some research showed that 1) is surprisingly common. But there
				# was no indication that it was caused by a bug in fman itself.
				# Maybe the users modified the source code of the Core plugin in
				# such a way that the file:// system failed to load.
				root = as_url(Path(sys.executable).anchor)
				try:
					pane.set_location(root)
				except Exception:
					_LOG.exception('Could not open %s.', root)
		if col_widths:
			try:
				pane.set_column_widths(col_widths)
			except ValueError:
				# This for instance happens when the old and new numbers of
				# columns don't match (eg. 2 columns before, 3 now).
				pass
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