from core.fileoperations import CopyFiles, MoveFiles
from core.github import find_repos, GitHubRepo
from core.os_ import open_terminal_in_directory, open_native_file_manager, \
	get_popen_kwargs_for_opening
from core.util import strformat_dict_values, listdir_absolute
from core.quicksearch_matchers import path_starts_with, basename_starts_with, \
	contains_chars, contains_chars_after_separator
from fman import *
from fman.fs import exists, touch, mkdir, is_dir, move, move_to_trash, delete, \
	samefile, copy, iterdir
from fman.url import splitscheme, as_url, join, basename, as_human_readable, \
	dirname
from getpass import getuser
from io import UnsupportedOperation
from itertools import chain, islice
from os.path import splitdrive, basename, normpath, expanduser, isabs, pardir, \
	islink
from pathlib import PurePath, Path
from PyQt5.QtCore import QFileInfo, QUrl
from PyQt5.QtGui import QDesktopServices
from shutil import rmtree
from subprocess import Popen, DEVNULL, PIPE
from tempfile import TemporaryDirectory

import fman
import fman.fs
import json
import os
import os.path
import re
import shutil
import sys

class About(ApplicationCommand):
	def __call__(self):
		msg = "fman version: " + FMAN_VERSION
		msg += "\n" + self._get_registration_info()
		show_alert(msg)
	def _get_registration_info(self):
		user_json_path = os.path.join(DATA_DIRECTORY, 'Local', 'User.json')
		try:
			with open(user_json_path, 'r') as f:
				data = json.load(f)
			return 'Registered to %s.' % data['email']
		except (FileNotFoundError, ValueError, KeyError):
			return 'Not registered.'

class Help(ApplicationCommand):

	aliases = ('Help', 'Show keyboard shortcuts', 'Show key bindings')

	def __call__(self):
		QDesktopServices.openUrl(QUrl('https://fman.io/docs/key-bindings?s=f'))

class _CorePaneCommand(DirectoryPaneCommand):
	def toggle_selection(self):
		file_under_cursor = self.pane.get_file_under_cursor()
		if file_under_cursor:
			self.pane.toggle_selection(file_under_cursor)

class MoveCursorDown(_CorePaneCommand):
	def __call__(self, toggle_selection=False):
		if toggle_selection:
			self.toggle_selection()
		self.pane.move_cursor_down()

class MoveCursorUp(_CorePaneCommand):
	def __call__(self, toggle_selection=False):
		if toggle_selection:
			self.toggle_selection()
		self.pane.move_cursor_up()

class MoveCursorHome(_CorePaneCommand):
	def __call__(self, toggle_selection=False):
		self.pane.move_cursor_home(toggle_selection)

class MoveCursorEnd(_CorePaneCommand):
	def __call__(self, toggle_selection=False):
		self.pane.move_cursor_end(toggle_selection)

class MoveCursorPageUp(_CorePaneCommand):
	def __call__(self, toggle_selection=False):
		self.pane.move_cursor_page_up(toggle_selection)
		self.pane.move_cursor_up()

class MoveCursorPageDown(_CorePaneCommand):
	def __call__(self, toggle_selection=False):
		self.pane.move_cursor_page_down(toggle_selection)
		self.pane.move_cursor_down()

class ToggleSelection(_CorePaneCommand):
	def __call__(self):
		self.toggle_selection()

class MoveToTrash(_CorePaneCommand):

	aliases = ('Delete', 'Move to trash', 'Move to recycle bin')

	def __call__(self, urls=None):
		if urls is None:
			urls = self.get_chosen_files()
		if not urls:
			show_alert('No file is selected!')
			return
		if len(urls) > 1:
			description = 'these %d items' % len(urls)
		else:
			description = as_human_readable(urls[0])
		trash = 'Recycle Bin' if PLATFORM == 'Windows' else 'Trash'
		choice = show_alert(
			"Do you really want to move %s to the %s?" % (description, trash),
			YES | NO, YES
		)
		if choice & YES:
			for url in urls:
				try:
					move_to_trash(url)
				except UnsupportedOperation:
					delete(url)

class DeletePermanently(DirectoryPaneCommand):
	def __call__(self, urls=None):
		if urls is None:
			urls = self.get_chosen_files()
		if not urls:
			show_alert('No file is selected!')
			return
		if len(urls) > 1:
			description = 'these %d items' % len(urls)
		else:
			description = as_human_readable(urls[0])
		choice = show_alert(
			"Do you really want to PERMANENTLY delete %s? This action cannot "
			"be undone!" % description,
			YES | NO, YES
		)
		if choice & YES:
			for file_path in urls:
				delete(file_path)

class GoUp(_CorePaneCommand):

	aliases = ('Go up', 'Go to parent directory')

	def __call__(self):
		path_before = self.pane.get_path()
		def callback():
			path_now = self.pane.get_path()
			# Only move the cursor if we actually changed directories; For
			# instance, we don't want to move the cursor if the user presses
			# Backspace while at drives:// and the cursor is already at
			# drives://C:
			if path_now != path_before:
				# Consider: The user is in zip:///Temp.zip and invokes GoUp.
				# This takes us to file:///. We want to place the cursor at
				# file:///Temp.zip. "Switch" schemes to make this happen:
				cursor_dest = splitscheme(path_now)[0] + \
							  splitscheme(path_before)[1]
				try:
					self.pane.place_cursor_at(cursor_dest)
				except ValueError as dest_doesnt_exist:
					self.pane.move_cursor_home()
		parent_dir = dirname(path_before)
		try:
			self.pane.set_path(parent_dir, callback)
		except FileNotFoundError:
			# This for instance happens when the user pressed backspace when at
			# file:/// on Unix.
			pass

class Open(_CorePaneCommand):
	def __call__(self, url=None):
		if url is None:
			url = self.pane.get_file_under_cursor()
		if url:
			# Use `run_command` to delegate the actual task of opening the file.
			# This makes it possible for plugins to modify the default open
			# behaviour by implementing DirectoryPaneListener#on_command(...).
			if is_dir(url):
				self.pane.run_command('open_directory', {'url': url})
			else:
				self.pane.run_command('open_file', {'url': url})
		else:
			show_alert('No file is selected!')

class OpenListener(DirectoryPaneListener):
	def on_doubleclicked(self, file_url):
		self.pane.run_command('open', {'url': file_url})

class OpenDirectory(DirectoryPaneCommand):
	def __call__(self, url):
		if is_dir(url):
			self.pane.set_path(url)
		else:
			def callback():
				self.pane.place_cursor_at(url)
			self.pane.set_path(dirname(url), callback=callback)
	def is_visible(self):
		return False

class OpenFile(DirectoryPaneCommand):
	def __call__(self, url):
		scheme, path = splitscheme(url)
		if scheme != 'file://':
			show_alert(
				'Opening files from %s is not supported. If you are a plugin '
				'developer, you can implement this with '
				'DirectoryPaneListener#on_command(...).' % scheme
			)
			return
		if PLATFORM == 'Linux':
			use_qt = False
			try:
				Popen([path], stdin=DEVNULL, stdout=DEVNULL, stderr=DEVNULL)
			except (OSError, ValueError):
				use_qt = True
		else:
			use_qt = True
		if use_qt:
			QDesktopServices.openUrl(QUrl.fromLocalFile(path))
	def is_visible(self):
		return False

class OpenWithEditor(_CorePaneCommand):

	aliases = ('Edit',)

	_PLATFORM_APPLICATIONS_FILTER = {
		'Mac': 'Applications (*.app)',
		'Windows': 'Applications (*.exe)',
		'Linux': 'Applications (*)'
	}
	def __call__(self, url=None):
		if url is None:
			url = self.pane.get_file_under_cursor()
		if not url:
			show_alert('No file is selected!')
			return
		scheme, path = splitscheme(url)
		if scheme != 'file://':
			show_alert(
				'Editing files from %s is not supported. If you are a plugin '
				'developer, you can implement this with '
				'DirectoryPaneListener#on_command(...).' % scheme
			)
			return
		editor = self._get_editor()
		if editor:
			popen_kwargs = strformat_dict_values(editor, {'file': path})
			Popen(**popen_kwargs)
	def _get_editor(self):
		settings = load_json('Core Settings.json', default={})
		result = settings.get('editor', {})
		if not result:
			choice = show_alert(
				'Editor is currently not configured. Please pick one.',
				OK | CANCEL, OK
			)
			if choice & OK:
				editor_path = show_file_open_dialog(
					'Pick an Editor', self._get_applications_directory(),
					self._PLATFORM_APPLICATIONS_FILTER[PLATFORM]
				)
				if editor_path:
					result = get_popen_kwargs_for_opening('{file}', editor_path)
					settings['editor'] = result
					save_json('Core Settings.json')
		return result
	def _get_applications_directory(self):
		if PLATFORM == 'Mac':
			return '/Applications'
		elif PLATFORM == 'Windows':
			result = _get_program_files()
			if not os.path.exists(result):
				result = _get_program_files_x86()
			if not os.path.exists(result):
				result = splitdrive(sys.executable)[0] + '\\'
			return result
		elif PLATFORM == 'Linux':
			return '/usr/bin'
		raise NotImplementedError(PLATFORM)

def _get_program_files():
	return os.environ.get('PROGRAMW6432', r'C:\Program Files')

def _get_program_files_x86():
	return os.environ.get('PROGRAMFILES', r'C:\Program Files (x86)')

class CreateAndEditFile(OpenWithEditor):

	aliases = ('New file', 'Create file', 'Create and edit file')

	def __call__(self, url=None):
		file_under_cursor = self.pane.get_file_under_cursor()
		if file_under_cursor and not is_dir(file_under_cursor):
			default_name = basename(file_under_cursor)
		else:
			default_name = ''
		file_name, ok = \
			show_prompt('Enter file name to create/edit:', default_name)
		if ok and file_name:
			file_to_edit = join(self.pane.get_path(), file_name)
			if not exists(file_to_edit):
				try:
					touch(file_to_edit)
				except PermissionError:
					show_alert(
						"You do not have enough permissions to create %s."
						% as_human_readable(file_to_edit)
					)
					return
			self.pane.place_cursor_at(file_to_edit)
			super().__call__(file_to_edit)

class _TreeCommand(_CorePaneCommand):
	def __call__(self, files=None, dest_dir=None):
		if files is None:
			files = self.get_chosen_files()
			src_dir = self.pane.get_path()
		else:
			# This for instance happens in Drag and Drop operations.
			src_dir = None
		if dest_dir is None:
			dest_dir = _get_opposite_pane(self.pane).get_path()
		proceed = self._confirm_tree_operation(files, dest_dir, src_dir)
		if proceed:
			dest_dir, dest_name = proceed
			self._call(files, dest_dir, src_dir, dest_name)
	def _call(self, files, dest_dir, src_dir=None, dest_name=None):
		raise NotImplementedError()
	@classmethod
	def _confirm_tree_operation(
		cls, files, dest_dir, src_dir, ui=fman, fs=fman.fs
	):
		if not files:
			ui.show_alert('No file is selected!')
			return
		if len(files) == 1:
			file_, = files
			dest_name = '' if fs.is_dir(file_) else basename(file_)
			files_descr = '"%s"' % basename(file_)
		else:
			dest_name = ''
			files_descr = '%d files' % len(files)
		descr_verb = cls.__name__
		message = '%s %s to' % (descr_verb, files_descr)
		dest = as_human_readable(join(dest_dir, dest_name))
		dest, ok = ui.show_prompt(message, dest)
		if dest and ok:
			dest = _from_human_readable(dest, dest_dir, src_dir)
			if fs.exists(dest):
				if fs.is_dir(dest):
					return dest, None
				else:
					if len(files) == 1:
						return _split(dest)
					else:
						ui.show_alert(
							'You cannot %s multiple files to a single file!' %
							descr_verb.lower()
						)
			else:
				if len(files) == 1:
					return _split(dest)
				else:
					choice = ui.show_alert(
						'%s does not exist. Do you want to create it '
						'as a directory and %s the files there?' %
						(as_human_readable(dest), descr_verb.lower()),
						YES | NO, YES
					)
					if choice & YES:
						return dest, None

def _get_opposite_pane(pane):
	panes = pane.window.get_panes()
	return panes[(panes.index(pane) + 1) % len(panes)]

def _from_human_readable(path_or_url, dest_dir, src_dir):
	try:
		splitscheme(path_or_url)
	except ValueError as no_scheme:
		dest_scheme, dest_dir_path = splitscheme(dest_dir)
		if src_dir:
			# Treat dest as relative to src_dir:
			src_scheme, src_path = splitscheme(src_dir)
			dest_path = PurePath(src_path, path_or_url).as_posix()
		else:
			dest_path = PurePath(dest_dir_path, path_or_url).as_posix()
		path_or_url = dest_scheme + dest_path
	return path_or_url

def _split(url):
	scheme, path = splitscheme(url)
	head, tail = os.path.split(path)
	return scheme + head, tail

class Copy(_TreeCommand):
	def _call(self, files, dest_dir, src_dir=None, dest_name=None):
		CopyFiles(fman, files, dest_dir, src_dir, dest_name)()

class Move(_TreeCommand):
	def _call(self, files, dest_dir, src_dir=None, dest_name=None):
		MoveFiles(fman, files, dest_dir, src_dir, dest_name)()

class DragAndDropListener(DirectoryPaneListener):
	def on_files_dropped(self, file_urls, dest_dir, is_copy_not_move):
		command = self._get_command(file_urls, dest_dir, is_copy_not_move)
		self.pane.run_command(
			command, {'files': file_urls, 'dest_dir': dest_dir}
		)
	def _get_command(self, file_urls, dest_dir, is_copy_not_move):
		schemes = set(splitscheme(url)[0] for url in file_urls)
		src_scheme = next(iter(schemes)) if len(schemes) == 1 else ''
		dest_scheme = splitscheme(dest_dir)
		if src_scheme != dest_scheme:
			# The default value for `is_copy_not_move` is False. But consider
			# the case where the user drags a file from a Zip archive to the
			# local file system. In this case, `is_copy_not_move` might indicate
			# "move" simply because it's the default. But most likely, the user
			# simply wants to extract the file and not also remove it from the
			# Zip file. Respect this:
			is_copy_not_move = True
		return 'copy' if is_copy_not_move else 'move'

class Rename(_CorePaneCommand):
	def __call__(self):
		file_under_cursor = self.pane.get_file_under_cursor()
		if file_under_cursor:
			self.pane.edit_name(file_under_cursor)
		else:
			show_alert('No file is selected!')

class RenameListener(DirectoryPaneListener):
	def on_name_edited(self, file_url, new_name):
		old_name = basename(file_url)
		if not new_name or new_name == old_name:
			return
		is_relative = \
			os.sep in new_name or new_name in (pardir, '.') \
			or (PLATFORM == 'Windows' and '/' in new_name)
		if is_relative:
			show_alert(
				'Relative paths are not supported. Please use Move (F6) '
				'instead.'
			)
			return
		new_url = join(dirname(file_url), new_name)
		if exists(new_url):
			# Don't show dialog when "Foo" was simply renamed to "foo":
			if not samefile(new_url, file_url):
				show_alert(new_name + ' already exists!')
				return
		try:
			move(file_url, new_url)
		except OSError as e:
			if isinstance(e, PermissionError):
				message = 'Access was denied trying to rename %s to %s.'
			else:
				message = 'Could not rename %s to %s.'
			show_alert(message % (old_name, new_name))
		else:
			self.pane.place_cursor_at(new_url)

class CreateDirectory(_CorePaneCommand):

	aliases = (
		'New folder', 'Create folder', 'New directory', 'Create directory'
	)

	def __call__(self):
		name, ok = show_prompt("New folder (directory)")
		if ok and name:
			dir_url = join(self.pane.get_path(), name)
			try:
				mkdir(dir_url)
			except FileExistsError:
				if is_dir(dir_url):
					show_alert("This directory already exists!")
				else:
					show_alert("A file with this name already exists!")
			self.pane.place_cursor_at(dir_url)

class OpenTerminal(_CorePaneCommand):

	aliases = (
		'Terminal', 'Shell', 'Open terminal', 'Open shell'
	)

	def __call__(self):
		scheme, path = splitscheme(self.pane.get_path())
		if scheme != 'file://':
			show_alert(
				"Can currently open the terminal only in local directories."
			)
			return
		open_terminal_in_directory(path)

class OpenNativeFileManager(_CorePaneCommand):
	def __call__(self):
		open_native_file_manager(self.pane.get_path())

class CopyPathsToClipboard(_CorePaneCommand):
	def __call__(self):
		chosen_files = self.get_chosen_files()
		if not chosen_files:
			show_alert('No file is selected!')
			return
		to_copy = [as_human_readable(url) for url in chosen_files]
		files = '\n'.join(to_copy)
		clipboard.clear()
		clipboard.set_text(files)

class CopyToClipboard(_CorePaneCommand):
	def __call__(self):
		files = self.get_chosen_files()
		if files:
			clipboard.copy_files(files)
		else:
			show_alert('No file is selected!')

class Cut(_CorePaneCommand):
	def __call__(self):
		if PLATFORM == 'Mac':
			show_alert(
				"Sorry, macOS doesn't support cutting files. Please press "
				"⌘-C (copy) followed by ⌘-⌥-V (move)."
			)
			return
		files = self.get_chosen_files()
		if files:
			clipboard.cut_files(files)
		else:
			show_alert('No file is selected!')

class Paste(_CorePaneCommand):
	def __call__(self):
		files = clipboard.get_files()
		if not files:
			return
		if clipboard.files_were_cut():
			self.pane.run_command('paste_cut')
		else:
			dest = self.pane.get_path()
			self.pane.run_command('copy', {'files': files, 'dest_dir': dest})

class PasteCut(_CorePaneCommand):
	def __call__(self):
		files = clipboard.get_files()
		if not any(map(exists, files)):
			# This can happen when the paste-cut has already been performed.
			return
		dest_dir = self.pane.get_path()
		self.pane.run_command('move', {
			'files': files,
			'dest_dir': dest_dir
		})

class SelectAll(_CorePaneCommand):
	def __call__(self):
		self.pane.select_all()

class Deselect(_CorePaneCommand):
	def __call__(self):
		self.pane.clear_selection()

class ToggleHiddenFiles(_CorePaneCommand):

	aliases = ('Toggle hidden files', 'Show / hide hidden files')

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		settings = load_json('Panes.json', default=[], save_on_quit=True)
		default = {'show_hidden_files': False}
		pane_index = self.pane.window.get_panes().index(self.pane)
		for _ in range(pane_index - len(settings) + 1):
			settings.append(default.copy())
		self.pane_info = settings[pane_index]
		self.pane._add_filter(self.should_display)
	def should_display(self, url):
		if self.show_hidden_files:
			return True
		if PLATFORM == 'Mac' and url == 'file:///Volumes':
			return True
		scheme, path = splitscheme(url)
		return scheme != 'file://' or not _is_hidden(path)
	def __call__(self):
		self.show_hidden_files = not self.show_hidden_files
		self.pane._invalidate_filters()
	@property
	def show_hidden_files(self):
		return self.pane_info['show_hidden_files']
	@show_hidden_files.setter
	def show_hidden_files(self, value):
		self.pane_info['show_hidden_files'] = value

def _is_hidden(file_path):
	return QFileInfo(file_path).isHidden()

class _OpenInPaneCommand(_CorePaneCommand):
	def __call__(self):
		panes = self.pane.window.get_panes()
		num_panes = len(panes)
		if num_panes < 2:
			raise NotImplementedError()
		this_pane = panes.index(self.pane)
		source_pane = panes[self.get_source_pane(this_pane, num_panes)]
		if source_pane is self.pane:
			to_open = source_pane.get_file_under_cursor() or \
					  source_pane.get_path()
		else:
			# This for instance happens when the right pane is active and the
			# user asks to "open in the right pane". The source pane in this
			# case is the left pane. The cursor in the left pane is not visible
			# (because the right pane is active) - but it still exists and might
			# be over a directory! If we opened the directory under the cursor,
			# we would thus open a subdirectory of the left pane. That's not
			# what we want. We want to open the directory of the left pane:
			to_open = source_pane.get_path()
		dest_pane = panes[self.get_destination_pane(this_pane, num_panes)]
		dest_pane.run_command('open_directory', {'url': to_open})
	def get_source_pane(self, this_pane, num_panes):
		raise NotImplementedError()
	def get_destination_pane(self, this_pane, num_panes):
		raise NotImplementedError()

class OpenInRightPane(_OpenInPaneCommand):
	def get_source_pane(self, this_pane, num_panes):
		if this_pane == num_panes - 1:
			return this_pane - 1
		return this_pane
	def get_destination_pane(self, this_pane, num_panes):
		return min(this_pane + 1, num_panes - 1)

class OpenInLeftPane(_OpenInPaneCommand):
	def get_source_pane(self, this_pane, num_panes):
		if this_pane > 0:
			return this_pane
		return 1
	def get_destination_pane(self, this_pane, num_panes):
		return max(this_pane - 1, 0)

class ShowVolumes(_CorePaneCommand):

	aliases = ('Show volumes', 'Show drives')

	def __call__(self, pane_index=None):
		if pane_index is None:
			pane = self.pane
		else:
			pane = self.pane.window.get_panes()[pane_index]
		def callback():
			pane.focus()
			pane.move_cursor_home()
		pane.set_path(_get_volumes_url(), callback=callback)

def _get_volumes_url():
	if PLATFORM == 'Mac':
		return 'file:///Volumes'
	elif PLATFORM == 'Windows':
		return 'drives://'
	elif PLATFORM == 'Linux':
		if os.path.isdir('/media'):
			contents = os.listdir('/media')
			user_name = _get_user()
			if contents == [user_name]:
				return as_url(os.path.join('/media', user_name))
			else:
				return 'file:///media'
		else:
			return 'file:///mnt'
	else:
		raise NotImplementedError(PLATFORM)

def _get_user():
	try:
		return getuser()
	except:
		return os.path.basename(expanduser('~'))

class GoTo(_CorePaneCommand):
	def __call__(self):
		# TODO: Rename to Visited Locations.json?
		visited_paths = load_json('Visited Paths.json', default={})
		_migrate_visited_paths(visited_paths)
		if not visited_paths:
			visited_paths.update({
				path: 0 for path in self._get_default_paths()
			})
		get_items = SuggestLocations(visited_paths)
		result = show_quicksearch(get_items, self._get_tab_completion)
		if result:
			query, suggested_dir = result
			path = ''
			if suggested_dir:
				path = expanduser(suggested_dir)
			if not os.path.isdir(path):
				path = expanduser(query)
			if not os.path.exists(path):
				# Maybe the user copy-pasted and there's some extra whitespace:
				path = path.rstrip()
			url = as_url(path)
			if os.path.isfile(path):
				self.pane.set_path(
					dirname(url),
					callback=lambda url=url: self.pane.place_cursor_at(url)
				)
			elif os.path.isdir(path):
				self.pane.set_path(url)
	def _get_tab_completion(self, curr_suggestion):
		result = curr_suggestion
		if not result.endswith(os.sep):
			result += os.sep
		return result
	def _get_default_paths(self):
		home_dir = expanduser('~')
		result = list(self._get_nonhidden_subdirs(home_dir))
		if PLATFORM == 'Windows':
			for candidate in (_get_program_files(), _get_program_files_x86()):
				if os.path.isdir(candidate):
					result.append(candidate)
		elif PLATFORM == 'Mac':
			result.append('/Volumes')
		elif PLATFORM == 'Linux':
			media_user = os.path.join('/media', _get_user())
			if os.path.exists(media_user):
				result.append(media_user)
			elif os.path.exists('/media'):
				result.append('/media')
			if os.path.exists('/mnt'):
				result.append('/mnt')
			# We need to add more suggestions on Linux, because unlike Windows
			# and Mac, we (currently) do not integrate with the OS's native
			# search functionality:
			result.extend(islice(self._traverse_by_mtime(home_dir), 500))
			result.extend(
				islice(self._traverse_by_mtime(
					'/', exclude={'/proc', '/sys'}), 500
				)
			)
		return result
	def _get_nonhidden_subdirs(self, dir_path):
		for file_name in os.listdir(dir_path):
			file_path = os.path.join(dir_path, file_name)
			if os.path.isdir(file_path) and not _is_hidden(file_path):
				yield os.path.join(dir_path, file_name)
	def _traverse_by_mtime(self, dir_path, exclude=None):
		if exclude is None:
			exclude = set()
		to_visit = [(os.stat(dir_path), dir_path)]
		already_yielded = set()
		while to_visit:
			stat, parent = to_visit.pop()
			if parent in exclude:
				continue
			yield parent
			try:
				parent_contents = os.listdir(parent)
			except OSError:
				continue
			for file_name in parent_contents:
				if file_name.startswith('.'):
					continue
				file_path = os.path.join(parent, file_name)
				try:
					if not os.path.isdir(file_path) or islink(file_path):
						continue
				except OSError:
					continue
				try:
					stat = os.stat(file_path)
				except OSError:
					pass
				else:
					already_yielded.add(stat.st_ino)
					to_visit.append((stat, file_path))
			to_visit.sort(key=lambda tpl: tpl[0].st_mtime)

# TODO: Remove this migration after November 2017
def _migrate_visited_paths(visited_paths):
	global _MIGRATED_VISITED_PATHS
	if _MIGRATED_VISITED_PATHS:
		return
	new_visited_paths = {
		expanduser(path): count
		for path, count in visited_paths.items()
	}
	visited_paths.clear()
	visited_paths.update(new_visited_paths)
	_MIGRATED_VISITED_PATHS = True

_MIGRATED_VISITED_PATHS = False

class GoToListener(DirectoryPaneListener):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.is_first_path_change = True
	def on_path_changed(self):
		if self.is_first_path_change:
			# on_path_changed() is also called when fman starts. Since this is
			# not a user-initiated path change, we don't want to count it:
			self.is_first_path_change = False
			return
		url = self.pane.get_path()
		scheme, path = splitscheme(url)
		if scheme != 'file://':
			return
		visited_paths = \
			load_json('Visited Paths.json', default={}, save_on_quit=True)
		# Ensure we're using backslashes \ on Windows:
		path = as_human_readable(url)
		visited_paths[path] = visited_paths.get(path, 0) + 1

def unexpand_user(path, expanduser_=expanduser):
	home_dir = expanduser_('~')
	if path.startswith(home_dir):
		path = '~' + path[len(home_dir):]
	return path

class SuggestLocations:

	_MATCHERS = (
		path_starts_with, basename_starts_with,
		contains_chars_after_separator(os.sep), contains_chars
	)

	class LocalFileSystem:
		def isdir(self, path):
			return os.path.isdir(path)
		def expanduser(self, path):
			return expanduser(path)
		def listdir(self, path):
			try:
				return os.listdir(path)
			except PermissionError:
				if PLATFORM == 'Windows' and self._is_documents_and_settings(
					path):
					# Python can't listdir("C:\Documents and Settings"). In
					# fact, no Windows program can. But "C:\{DaS}\<Username>"
					# does work, and displays "C:\Users\<Username>". For
					# consistency, treat DaS like a symlink to \Users:
					return os.listdir(splitdrive(path)[0] + r'\Users')
				raise
		def resolve(self, path):
			return str(Path(path).resolve())
		def samefile(self, f1, f2):
			return os.path.samefile(f1, f2)
		def find_folders_starting_with(self, pattern, timeout_secs=0.02):
			if PLATFORM == 'Mac':
				from objc import loadBundle
				ns = {}
				loadBundle(
					'CoreServices.framework', ns,
					bundle_identifier='com.apple.CoreServices'
				)
				pred = ns['NSPredicate'].predicateWithFormat_argumentArray_(
					"kMDItemContentType == 'public.folder' && "
					"kMDItemFSName BEGINSWITH[c] %@", [pattern]
				)
				query = ns['NSMetadataQuery'].alloc().init()
				query.setPredicate_(pred)
				query.setSearchScopes_(ns['NSArray'].arrayWithObject_('/'))
				query.startQuery()
				ns['NSRunLoop'].currentRunLoop().runUntilDate_(
					ns['NSDate'].dateWithTimeIntervalSinceNow_(timeout_secs)
				)
				query.stopQuery()
				for item in query.results():
					yield item.valueForAttribute_("kMDItemPath")
			elif PLATFORM == 'Windows':
				import adodbapi
				from pythoncom import com_error
				try:
					conn = adodbapi.connect(
						"Provider=Search.CollatorDSO;"
						"Extended Properties='Application=Windows';"
					)
					cursor = conn.cursor()

					# adodbapi claims to support "paramstyles", which would let us
					# pass parameters as an extra arg to .execute(...), without
					# having to worry about escaping them. Alas, adodbapi raises an
					# error when this feature is used. We thus have to escape the
					# param ourselves:
					def escape(param):
						return re.subn(r'([%_\[\]\^])', r'[\1]', param)[0]

					cursor.execute(
						"SELECT TOP 5 System.ItemPathDisplay FROM SYSTEMINDEX "
						"WHERE "
						"System.ItemType = 'Directory' AND "
						"System.ItemNameDisplay LIKE %r "
						"ORDER BY System.ItemPathDisplay"
						% (escape(pattern) + '%')
					)
					for row in iter(cursor.fetchone, None):
						value = row['System.ItemPathDisplay']
						# Seems to be None sometimes:
						if value:
							yield value
				except (adodbapi.Error, com_error):
					pass
		def _is_documents_and_settings(self, path):
			return splitdrive(normpath(path))[1].lower() == \
				   '\\documents and settings'

	def __init__(self, visited_paths, file_system=None):
		if file_system is None:
			# Encapsulating filesystem-related functionality in a separate field
			# allows us to use a different implementation for testing.
			file_system = self.LocalFileSystem()
		self.visited_paths = visited_paths
		self.fs = file_system
	def __call__(self, query):
		possible_dirs = self._gather_dirs(query)
		items = self._filter_matching(possible_dirs, query)
		return self._remove_nonexistent(items)
	def _gather_dirs(self, query):
		path = normpath(self.fs.expanduser(query))
		if PLATFORM == 'Windows':
			# Windows completely ignores trailing spaces in directory names at
			# all times. Make our implementation reflect this:
			path = path.rstrip(' ')
			# Handle the case where the user has entered a drive such as 'E:'
			# without the trailing backslash:
			if re.match(r'^[A-Z]:$', path):
				path += '\\'
		if isabs(path):
			get_subdirs = lambda dir_: self._sort(self._gather_subdirs(dir_))
			if self.fs.isdir(path):
				dir_ = self.fs.resolve(path)
				return [dir_] + get_subdirs(dir_)
			elif self.fs.isdir(os.path.dirname(path)):
				return get_subdirs(self.fs.resolve(os.path.dirname(path)))
		result = set(self.visited_paths)
		if len(query) > 2:
			"""Compensate for directories not yet in self.visited_paths:"""
			fs_folders = islice(self.fs.find_folders_starting_with(query), 100)
			result.update(self._sort(fs_folders)[:10])
		return self._sort(result)
	def _sort(self, dirs):
		return sorted(dirs, key=lambda dir_: (
			-self.visited_paths.get(dir_, 0), len(dir_), dir_.lower()
		))
	def _filter_matching(self, dirs, query):
		use_tilde = \
			not query.startswith(os.path.dirname(self.fs.expanduser('~')))
		result = [[] for _ in self._MATCHERS]
		for dir_ in dirs:
			title = self._unexpand_user(dir_) if use_tilde else dir_
			for i, matcher in enumerate(self._MATCHERS):
				match = matcher(title.lower(), query.lower())
				if match is not None:
					result[i].append(QuicksearchItem(
						dir_, title, highlight=match
					))
					break
		return list(chain.from_iterable(result))
	def _remove_nonexistent(self, items):
		for item in items:
			dir_ = item.value
			if self.fs.isdir(self.fs.expanduser(dir_)):
				yield item
			else:
				try:
					del self.visited_paths[dir_]
				except KeyError:
					pass
	def _gather_subdirs(self, dir_):
		try:
			dir_contents = self.fs.listdir(dir_)
		except OSError:
			pass
		else:
			for name in dir_contents:
				file_path = os.path.join(dir_, name)
				if self.fs.isdir(file_path):
					yield file_path
	def _unexpand_user(self, path):
		return unexpand_user(path, self.fs.expanduser)

class CommandPalette(_CorePaneCommand):

	_MATCHERS = (contains_chars_after_separator(' '), contains_chars)

	_KEY_SYMBOLS_MAC = {
		'Cmd': '⌘', 'Alt': '⌥', 'Ctrl': '⌃', 'Shift': '⇧', 'Backspace': '⌫',
		'Up': '↑', 'Down': '↓', 'Left': '←', 'Right': '→', 'Enter': '↩'
	}

	def __call__(self):
		result = show_quicksearch(self._suggest_commands)
		if result:
			command = result[1]
			if command:
				command()
	def _suggest_commands(self, query):
		result = [[] for _ in self._MATCHERS]
		for cmd_name, aliases, command in self._get_all_commands():
			for alias in aliases:
				this_alias_matched = False
				for i, matcher in enumerate(self._MATCHERS):
					match = matcher(alias.lower(), query.lower())
					if match is not None:
						shortcuts = self._get_shortcuts_for_command(cmd_name)
						hint = ', '.join(shortcuts)
						item = QuicksearchItem(command, alias, match, hint)
						result[i].append(item)
						this_alias_matched = True
						break
				if this_alias_matched:
					# Don't check the other aliases:
					break
		for results in result:
			results.sort(key=lambda item: (len(item.title), item.title))
		return chain.from_iterable(result)
	def _get_all_commands(self):
		result = []
		for cmd_name in self.pane.get_commands():
			if not self.pane.is_command_visible(cmd_name):
				continue
			# https://docs.python.org/3/faq/programming.html#why-do-lambdas-
			# defined-in-a-loop-with-different-values-all-return-the-same-result
			aliases = self.pane.get_command_aliases(cmd_name)
			command = lambda cmd=cmd_name: self.pane.run_command(cmd)
			result.append((cmd_name, aliases, command))
		for cmd_name in get_application_commands():
			aliases = get_application_command_aliases(cmd_name)
			# https://docs.python.org/3/faq/programming.html#why-do-lambdas-
			# defined-in-a-loop-with-different-values-all-return-the-same-result
			command = lambda cmd=cmd_name: run_application_command(cmd)
			result.append((cmd_name, aliases, command))
		return result
	def _get_shortcuts_for_command(self, command):
		for binding in load_json('Key Bindings.json'):
			if binding['command'] == command:
				shortcut = binding['keys'][0]
				if PLATFORM == 'Mac':
					shortcut = self._insert_mac_key_symbols(shortcut)
				yield shortcut
	def _insert_mac_key_symbols(self, shortcut):
		keys = shortcut.split('+')
		return ''.join(self._KEY_SYMBOLS_MAC.get(key, key) for key in keys)

class Quit(ApplicationCommand):

	aliases = ('Quit', 'Exit')

	def __call__(self):
		sys.exit(0)

class InstallLicenseKey(DirectoryPaneCommand):
	def __call__(self):
		scheme, curr_dirpath = splitscheme(self.pane.get_path())
		if scheme != 'file://':
			show_alert(
				'Sorry, please copy User.json to your local file system first.'
			)
			return
		license_key = os.path.join(curr_dirpath, 'User.json')
		if not os.path.exists(license_key):
			show_alert(
				'Could not find license key file "User.json" in the current '
				'directory %s.' % curr_dirpath
			)
			return
		destination_directory = os.path.join(DATA_DIRECTORY, 'Local')
		shutil.copy(license_key, destination_directory)
		show_alert(
			"Thank you! Please restart fman to complete the registration. You "
			"should no longer see the annoying popup when it starts."
		)

class ZenOfFman(ApplicationCommand):
	def __call__(self):
		show_alert(
			"The Zen of fman\n"
			"https://fman.io/zen\n\n"
			"Looks matter\n"
			"Speed counts\n"
			"Extending must be easy\n"
			"Customisability is important\n"
			"But not at the expense of speed\n"
			"I/O is better asynchronous\n"
			"Updates should be transparent and continuous\n"
			"Don't reinvent the wheel"
		)

class OpenDataDirectory(DirectoryPaneCommand):
	def __call__(self):
		self.pane.set_path(as_url(DATA_DIRECTORY))

class GoBack(DirectoryPaneCommand):
	def __call__(self):
		HistoryListener.INSTANCES[self.pane].go_back()

class GoForward(DirectoryPaneCommand):
	def __call__(self):
		HistoryListener.INSTANCES[self.pane].go_forward()

class HistoryListener(DirectoryPaneListener):

	INSTANCES = {}

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._history = History()
		self.INSTANCES[self.pane] = self
	def go_back(self):
		try:
			path = self._history.go_back()
		except ValueError:
			return
		self.pane.set_path(path)
	def go_forward(self):
		try:
			path = self._history.go_forward()
		except ValueError:
			return
		self.pane.set_path(path)
	def on_path_changed(self):
		self._history.path_changed(self.pane.get_path())

class History:
	def __init__(self):
		self._paths = []
		self._curr_path = -1
		self._ignore_next_path_change = False
	def go_back(self):
		if self._curr_path <= 0:
			raise ValueError()
		self._curr_path -= 1
		self._ignore_next_path_change = True
		return self._paths[self._curr_path]
	def go_forward(self):
		if self._curr_path >= len(self._paths) - 1:
			raise ValueError()
		self._curr_path += 1
		self._ignore_next_path_change = True
		return self._paths[self._curr_path]
	def path_changed(self, path):
		if self._ignore_next_path_change:
			self._ignore_next_path_change = False
			return
		self._curr_path += 1
		del self._paths[self._curr_path:]
		self._paths.append(path)

class InstallPlugin(ApplicationCommand):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._plugin_repos = None
	def __call__(self, github_repo=None):
		if github_repo:
			with StatusMessage('Fetching GitHub repo %s...' % github_repo):
				repo = GitHubRepo.fetch(github_repo)
		else:
			if self._plugin_repos is None:
				with StatusMessage('Fetching available plugins...'):
					self._plugin_repos = find_repos(topics=['fman', 'plugin'])
			result = show_quicksearch(self._get_matching_repos)
			repo = result[1] if result else None
		if repo:
			with StatusMessage('Downloading %s...' % repo.name):
				try:
					ref = repo.get_latest_release()
				except LookupError as no_release_yet:
					ref = repo.get_latest_commit()
				zipball_contents = repo.download_zipball(ref)
			dest_dir = self._install_plugin(repo.name, zipball_contents)
			# Save some data in case we want to update the plugin later:
			self._record_plugin_installation(dest_dir, repo.url, ref)
			success = load_plugin(dest_dir)
			if success:
				show_alert('Plugin %r was successfully installed.' % repo.name)
	def _get_matching_repos(self, query):
		installed_plugins = set(
			os.path.basename(plugin_dir)
			for plugin_dir in _get_thirdparty_plugins()
		)
		for repo in self._plugin_repos:
			if repo.name in installed_plugins:
				continue
			match = contains_chars(repo.name.lower(), query.lower())
			if match or not query:
				hint = '%d ★' % repo.num_stars if repo.num_stars else ''
				yield QuicksearchItem(
					repo, repo.name, match, hint=hint,
					description=repo.description
				)
	def _install_plugin(self, name, zipball_contents):
		dest_dir = os.path.join(_THIRDPARTY_PLUGINS_DIR, name)
		dest_dir_url = as_url(dest_dir)
		if exists(dest_dir_url):
			raise ValueError('Plugin %s seems to already be installed.' % name)
		# We purposely don't use Python's ZipFile here because it does not
		# preserve the executable bit of extracted files. This would present a
		# problem for plugins shipping with their own binaries.
		with TemporaryDirectory() as tmp_dir:
			zip_path = os.path.join(tmp_dir, 'plugin.zip')
			with open(zip_path, 'wb') as f:
				f.write(zipball_contents)
			zip_url = as_url(zip_path, 'zip://')
			dir_in_zip, = iterdir(zip_url)
			copy(join(zip_url, dir_in_zip), dest_dir_url)
		return dest_dir
	def _record_plugin_installation(self, plugin_dir, repo_url, ref):
		plugin_json = os.path.join(plugin_dir, 'Plugin.json')
		if os.path.exists(plugin_json):
			with open(plugin_json, 'r') as f:
				data = json.load(f)
		else:
			data = {}
		data['url'] = repo_url
		data['ref'] = ref
		with open(plugin_json, 'w') as f:
			json.dump(data, f)

_THIRDPARTY_PLUGINS_DIR = os.path.join(DATA_DIRECTORY, 'Plugins', 'Third-party')

def _get_thirdparty_plugins():
	return _list_plugins(_THIRDPARTY_PLUGINS_DIR)

def _list_plugins(dir_path):
	try:
		return list(filter(os.path.isdir, listdir_absolute(dir_path)))
	except FileNotFoundError:
		return []

class RemovePlugin(ApplicationCommand):

	aliases = ('Remove plugin', 'Uninstall plugin')

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._installed_plugins = None
	def __call__(self):
		self._installed_plugins = _get_thirdparty_plugins()
		if not self._installed_plugins:
			show_alert("You don't seem to have any plugins installed.")
		else:
			result = show_quicksearch(self._get_matching_plugins)
			if result:
				plugin_dir = result[1]
				if plugin_dir:
					try:
						unload_plugin(plugin_dir)
					except ValueError as plugin_was_not_loaded:
						pass
					rmtree(plugin_dir)
					show_alert(
						'Plugin %r was successfully removed.'
						% os.path.basename(plugin_dir)
					)
	def _get_matching_plugins(self, query):
		for plugin_dir in self._installed_plugins:
			plugin_name = os.path.basename(plugin_dir)
			match = contains_chars(plugin_name.lower(), query.lower())
			if match or not query:
				yield QuicksearchItem(plugin_dir, plugin_name, highlight=match)

class ReloadPlugins(ApplicationCommand):
	def __call__(self):
		# When a pane is currently displaying a location with a file system that
		# is "reloaded", its location gets lost. So save the locations and
		# restore them below:
		paths_before = [pane.get_path() for pane in (self.window.get_panes())]
		plugins = _get_plugins()
		for plugin in reversed(plugins):
			try:
				unload_plugin(plugin)
			except ValueError as plugin_had_not_been_loaded:
				pass
		for plugin in plugins:
			load_plugin(plugin)
		for pane, path in zip(self.window.get_panes(), paths_before):
			pane.set_path(path)
		num_plugins = len(plugins)
		plural = 's' if num_plugins > 1 else ''
		show_status_message(
			'Reloaded %d plugin%s.' % (num_plugins, plural), timeout_secs=2
		)

def _get_plugins():
	return _get_thirdparty_plugins() + _get_user_plugins()

def _get_user_plugins():
	result = []
	settings_plugin = ''
	user_plugins_dir = os.path.join(DATA_DIRECTORY, 'Plugins', 'User')
	for plugin_dir in _list_plugins(user_plugins_dir):
		if os.path.basename(plugin_dir) == 'Settings':
			settings_plugin = plugin_dir
		else:
			result.append(plugin_dir)
	# According to the fman docs, the Settings plugin is loaded last:
	if settings_plugin:
		result.append(settings_plugin)
	return result

class ListPlugins(DirectoryPaneCommand):
	def __call__(self):
		result = show_quicksearch(self._get_matching_plugins)
		if result:
			plugin_dir = result[1]
			if plugin_dir:
				self.pane.set_path(as_url(plugin_dir))
	def _get_matching_plugins(self, query):
		result = []
		for plugin_dir in _get_thirdparty_plugins():
			plugin_name = os.path.basename(plugin_dir)
			match = contains_chars(plugin_name.lower(), query.lower())
			if match or not query:
				plugin_json = os.path.join(plugin_dir, 'Plugin.json')
				with open(plugin_json, 'r') as f:
					ref = json.load(f).get('ref', '')
				is_sha = len(ref) == 40
				if is_sha:
					ref = ref[:8]
				result.append(QuicksearchItem(
					plugin_dir, plugin_name, highlight=match, hint=ref
				))
		for plugin_dir in _get_user_plugins():
			plugin_name = os.path.basename(plugin_dir)
			match = contains_chars(plugin_name.lower(), query.lower())
			if match or not query:
				result.append(
					QuicksearchItem(plugin_dir, plugin_name, highlight=match)
				)
		return sorted(result, key=lambda qsi: qsi.title)

class StatusMessage:
	def __init__(self, message):
		self._message = message
	def __enter__(self):
		show_status_message(self._message)
	def __exit__(self, *_):
		clear_status_message()

if PLATFORM == 'Mac':
	class GetInfo(DirectoryPaneCommand):
		def __call__(self):
			files = self.get_chosen_files() or [self.pane.get_path()]
			self._run_applescript(
				'on run args\n'
				'	tell app "Finder"\n'
				'		activate\n'
				'		repeat with f in args\n'
				'			open information window of '
							'(posix file (contents of f) as alias)\n'
				'		end\n'
				'	end\n'
				'end\n',
				_get_local_filepaths(files)
			)
		def _run_applescript(self, script, args=None):
			if args is None:
				args = []
			process = Popen(
				['osascript', '-'] + args, stdin=PIPE,
				stdout=DEVNULL, stderr=DEVNULL
			)
			process.communicate(script.encode('ascii'))

def _get_local_filepaths(urls):
	result = []
	for url in urls:
		scheme, path = splitscheme(url)
		if scheme == 'file://':
			result.append(path)
	return result

class Pack(DirectoryPaneCommand):
	def __call__(self):
		files = self.get_chosen_files()
		if not files:
			show_alert('No file is selected!')
			return
		if len(files) == 1:
			descr = basename(files[0])
			dest_name = PurePath(basename(files[0])).stem + '.zip'
		else:
			descr = '%d files' % len(files)
			dest_name = basename(self.pane.get_path()) + '.zip'
		dest_dir = _get_opposite_pane(self.pane).get_path()
		dest_url = join(dest_dir, dest_name)
		dest, ok = \
			show_prompt('Pack %s to:' % descr, as_human_readable(dest_url))
		if dest and ok:
			dest = _from_human_readable(dest, dest_dir, self.pane.get_path())
			scheme = _get_handler_for_archive(basename(dest))
			if not scheme:
				show_alert('Sorry, but this archive format is not supported.')
				return
			dest_rewritten = scheme + splitscheme(dest)[1]
			try:
				# Create empty archive:
				mkdir(dest_rewritten)
			except FileExistsError:
				answer = show_alert(
					'%s already exists. Do you want to add/update the selected '
					'files?' % basename(dest_rewritten), YES | NO, YES
				)
				if not answer & YES:
					return
			for file_url in files:
				file_name = basename(file_url)
				with StatusMessage('Packing %s...' % file_name):
					copy(file_url, join(dest_rewritten, file_name))

def _get_handler_for_archive(file_name):
	settings = load_json('Core Settings.json', default={})
	archive_types = sorted(
		settings.get('archive_handlers', {}).items(),
		key=lambda tpl: -len(tpl[0])
	)
	for suffix, scheme in archive_types:
		if file_name.endswith(suffix):
			return scheme

class ArchiveOpenListener(DirectoryPaneListener):
	def on_command(self, command, args):
		if command in ('open_file', 'open_directory'):
			try:
				scheme, path = splitscheme(args['url'])
			except (KeyError, ValueError):
				return None
			if scheme == 'file://':
				new_scheme = _get_handler_for_archive(basename(path))
				if new_scheme:
					new_args = dict(args)
					new_args['url'] = new_scheme + path
					return 'open_directory', new_args

class Reload(DirectoryPaneCommand):

	aliases = ('Reload', 'Refresh')

	def __call__(self):
		self.pane.reload()