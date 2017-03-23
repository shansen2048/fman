from core import clipboard
from core.fileoperations import CopyFiles, MoveFiles
from core.os_ import open_terminal_in_directory, open_native_file_manager, \
	get_popen_kwargs_for_opening
from core.util import strformat_dict_values
from core.quicksearch_matchers import path_starts_with, basename_starts_with, \
	contains_chars, contains_chars_after_separator
from core.trash import move_to_trash
from fman import DirectoryPaneCommand, YES, NO, OK, CANCEL, load_json, \
	PLATFORM, DirectoryPaneListener, show_quicksearch, show_prompt, save_json, \
	show_alert, QuicksearchItem, DATA_DIRECTORY, FMAN_VERSION
from getpass import getuser
from itertools import chain
from ordered_set import OrderedSet
from os import mkdir, rename, listdir
from os.path import join, isfile, exists, splitdrive, basename, normpath, \
	isdir, split, dirname, realpath, expanduser, samefile, isabs, pardir
from PyQt5.QtCore import QFileInfo, QUrl
from PyQt5.QtGui import QDesktopServices
from shutil import copy
from subprocess import Popen, DEVNULL
from threading import Thread

import fman
import json
import os
import sys

class About(DirectoryPaneCommand):
	def __call__(self):
		msg = "fman version: " + FMAN_VERSION
		msg += "\n" + self._get_registration_info()
		show_alert(msg)
	def _get_registration_info(self):
		user_json_path = join(DATA_DIRECTORY, 'Local', 'User.json')
		try:
			with open(user_json_path, 'r') as f:
				data = json.load(f)
			return 'Registered to %s.' % data['email']
		except (FileNotFoundError, ValueError, KeyError):
			return 'Not registered.'

class Help(DirectoryPaneCommand):
	def __call__(self):
		QDesktopServices.openUrl(QUrl('https://fman.io/docs/key-bindings'))

class _CorePaneCommand(DirectoryPaneCommand):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		# The field `ui` is useful for automated tests: Tests can overwrite it
		# with a stub implementation to run without an actual GUI.
		self.ui = fman
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
	def __call__(self):
		to_delete = self.get_chosen_files()
		if not to_delete:
			show_alert('No file is selected!')
			return
		if len(to_delete) > 1:
			description = 'these %d items' % len(to_delete)
		else:
			description = to_delete[0]
		trash = 'Recycle Bin' if PLATFORM == 'Windows' else 'Trash'
		choice = self.ui.show_alert(
			"Do you really want to move %s to the %s?" % (description, trash),
			YES | NO, YES
		)
		if choice & YES:
			move_to_trash(*to_delete)

class GoUp(_CorePaneCommand):
	def __call__(self):
		current_dir = self.pane.get_path()
		if current_dir == '/':
			# We catch this case because the callback below doesn't handle it.
			# Consider: current_dir is '/'. Say the cursor is at /bin. We want
			# it to stay there. But the callback would attempt to place it at /.
			# This doesn't make sense.
			return
		callback = lambda: self.pane.place_cursor_at(current_dir)
		self.pane.set_path(dirname(current_dir), callback)

class Open(_CorePaneCommand):
	def __call__(self):
		file_under_cursor = self.pane.get_file_under_cursor()
		if file_under_cursor:
			_open(self.pane, file_under_cursor)
		else:
			show_alert('No file is selected!')

class OpenListener(DirectoryPaneListener):
	def on_doubleclicked(self, file_path):
		_open(self.pane, file_path)

def _open(pane, file_path):
	if isdir(file_path):
		pane.set_path(realpath(file_path))
	else:
		if PLATFORM == 'Linux':
			use_qt = False
			try:
				Popen(
					[file_path], stdin=DEVNULL, stdout=DEVNULL, stderr=DEVNULL
				)
			except (OSError, ValueError):
				use_qt = True
		else:
			use_qt = True
		if use_qt:
			QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))

class OpenWithEditor(_CorePaneCommand):
	_PLATFORM_APPLICATIONS_FILTER = {
		'Mac': 'Applications (*.app)',
		'Windows': 'Applications (*.exe)',
		'Linux': 'Applications (*)'
	}
	def __call__(self, create_new=False):
		file_under_cursor = self.pane.get_file_under_cursor()
		file_to_edit = file_under_cursor
		if create_new:
			if isfile(file_under_cursor):
				default_name = basename(file_under_cursor)
			else:
				default_name = ''
			file_name, ok = \
				show_prompt('Enter file name to create/edit:', default_name)
			if not ok or not file_name:
				return
			if ok and file_name:
				file_to_edit = join(self.pane.get_path(), file_name)
				if not exists(file_to_edit):
					open(file_to_edit, 'w').close()
				self.pane.place_cursor_at(file_to_edit)
		if exists(file_to_edit):
			self._open_with_editor(file_to_edit)
		else:
			show_alert('No file is selected!')
	def _open_with_editor(self, file_path):
		settings = load_json('Core Settings.json', default={})
		editor = settings.get('editor', {})
		if isinstance(editor, str):
			# TODO: Remove this migration after Feb, 2017.
			editor = get_popen_kwargs_for_opening('{file}', with_=editor)
			settings['editor'] = editor
			save_json('Core Settings.json')
		if not editor:
			choice = self.ui.show_alert(
				'Editor is currently not configured. Please pick one.',
				OK | CANCEL, OK
			)
			if choice & OK:
				editor_path = self.ui.show_file_open_dialog(
					'Pick an Editor', self._get_applications_directory(),
					self._PLATFORM_APPLICATIONS_FILTER[PLATFORM]
				)
				if editor_path:
					editor = get_popen_kwargs_for_opening('{file}', editor_path)
					settings['editor'] = editor
					save_json('Core Settings.json')
		if editor:
			popen_kwargs = strformat_dict_values(editor, {'file': file_path})
			Popen(**popen_kwargs)
	def _get_applications_directory(self):
		if PLATFORM == 'Mac':
			return '/Applications'
		elif PLATFORM == 'Windows':
			result = r'c:\Program Files'
			if not exists(result):
				result = splitdrive(sys.executable)[0] + '\\'
			return result
		elif PLATFORM == 'Linux':
			return '/usr/bin'
		raise NotImplementedError(PLATFORM)

class _TreeCommand(_CorePaneCommand):
	def __call__(self, files=None, dest_dir=None):
		if files is None:
			files = self.get_chosen_files()
			src_dir = self.pane.get_path()
		else:
			src_dir=None
		if dest_dir is None:
			dest_dir = self.other_pane.get_path()
		proceed = self._confirm_tree_operation(files, dest_dir, src_dir)
		if proceed:
			dest_dir, dest_name = proceed
			self._call(files, dest_dir, src_dir, dest_name)
	def _call(self, files, dest_dir, src_dir=None, dest_name=None):
		raise NotImplementedError()
	@property
	def other_pane(self):
		panes = self.pane.window.get_panes()
		return panes[(panes.index(self.pane) + 1) % len(panes)]
	def _confirm_tree_operation(self, files, dest_dir, src_dir):
		if not files:
			show_alert('No file is selected!')
			return
		if len(files) == 1:
			file_, = files
			dest_name = basename(file_) if isfile(file_) else ''
			files_descr = '"%s"' % basename(file_)
		else:
			dest_name = ''
			files_descr = '%d files' % len(files)
		descr_verb = self.__class__.__name__
		message = '%s %s to' % (descr_verb, files_descr)
		dest = normpath(join(dest_dir, dest_name))
		dest, ok = self.ui.show_prompt(message, dest)
		if ok:
			if not isabs(dest):
				dest = join(src_dir, dest)
			if exists(dest):
				if isdir(dest):
					return dest, None
				else:
					if len(files) == 1:
						return split(dest)
					else:
						self.ui.show_alert(
							'You cannot %s multiple files to a single file!' %
							descr_verb.lower()
						)
			else:
				if len(files) == 1:
					return split(dest)
				else:
					choice = self.ui.show_alert(
						'%s does not exist. Do you want to create it '
						'as a directory and %s the files there?' %
						(dest, descr_verb.lower()), YES | NO, YES
					)
					if choice & YES:
						return dest, None

class Copy(_TreeCommand):
	def _call(self, files, dest_dir, src_dir=None, dest_name=None):
		copy = CopyFiles(self.ui, files, dest_dir, src_dir, dest_name)
		Thread(target=copy).start()

class Move(_TreeCommand):
	def _call(self, files, dest_dir, src_dir=None, dest_name=None):
		move = MoveFiles(self.ui, files, dest_dir, src_dir, dest_name)
		Thread(target=move).start()

class DragAndDropListener(DirectoryPaneListener):
	def on_files_dropped(self, files, dest_dir, is_copy_not_move):
		command = 'copy' if is_copy_not_move else 'move'
		self.pane.run_command(command, {'files': files, 'dest_dir': dest_dir})

class Rename(_CorePaneCommand):
	def __call__(self):
		file_under_cursor = self.pane.get_file_under_cursor()
		if file_under_cursor:
			self.pane.edit_name(file_under_cursor)
		else:
			show_alert('No file is selected!')

class RenameListener(DirectoryPaneListener):
	def on_name_edited(self, file_path, new_name):
		old_name = basename(file_path)
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
		new_path = join(dirname(file_path), new_name)
		do_rename = True
		if exists(new_path):
			# Don't show dialog when "Foo" was simply renamed to "foo":
			if not samefile(new_path, file_path):
				response = show_alert(
					new_name + ' already exists. Do you want to overwrite it?',
					buttons=YES|NO, default_button=NO
				)
				do_rename = response & YES
		if do_rename:
			try:
				rename(file_path, new_path)
			except OSError as e:
				if isinstance(e, PermissionError):
					message = 'Access was denied trying to rename %s to %s.'
				else:
					message = 'Could not rename %s to %s.'
				show_alert(message % (old_name, new_name))
			else:
				self.pane.place_cursor_at(new_path)

class CreateDirectory(_CorePaneCommand):
	def __call__(self):
		name, ok = self.ui.show_prompt("New folder (directory)")
		if ok and name:
			dir_path = join(self.pane.get_path(), name)
			mkdir(dir_path)
			self.pane.place_cursor_at(dir_path)

class OpenTerminal(_CorePaneCommand):
	def __call__(self):
		open_terminal_in_directory(self.pane.get_path())

class OpenNativeFileManager(_CorePaneCommand):
	def __call__(self):
		open_native_file_manager(self.pane.get_path())

class CopyPathsToClipboard(_CorePaneCommand):
	def __call__(self):
		chosen_files = self.get_chosen_files()
		if not chosen_files:
			show_alert('No file is selected!')
			return
		files = '\n'.join(chosen_files)
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
		self.pane.run_command('move', {'files': files, 'dest_dir': dest_dir})

class SelectAll(_CorePaneCommand):
	def __call__(self):
		self.pane.select_all()

class Deselect(_CorePaneCommand):
	def __call__(self):
		self.pane.clear_selection()

class ToggleHiddenFiles(_CorePaneCommand):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		settings = load_json('Panes.json', default=[], save_on_quit=True)
		default = {'show_hidden_files': False}
		pane_index = self.pane.window.get_panes().index(self.pane)
		for _ in range(pane_index - len(settings) + 1):
			settings.append(default.copy())
		self.pane_info = settings[pane_index]
		self.pane._add_filter(self.should_display)
	def should_display(self, file_path):
		if self.show_hidden_files:
			return True
		if PLATFORM == 'Mac' and file_path == '/Volumes':
			return True
		return not _is_hidden(file_path)
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
			to_open = source_pane.get_file_under_cursor()
		else:
			# This for instance happens when the right pane is active and the
			# user asks to "open in the right pane". The source pane in this
			# case is the left pane. The cursor in the left pane is not visible
			# (because the right pane is active) - but it still exists and might
			# be over a directory! If we opened the directory under the cursor,
			# we would thus open a subdirectory of the left pane. That's not
			# what we want. We want to open the directory of the left pane:
			to_open = source_pane.get_path()
		if not isdir(to_open):
			to_open = dirname(to_open)
		dest_pane = panes[self.get_destination_pane(this_pane, num_panes)]
		dest_pane.set_path(to_open)
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
	def __call__(self, pane_index=None):
		if pane_index is None:
			pane = self.pane
		else:
			pane = self.pane.window.get_panes()[pane_index]
		pane.set_path(_get_volumes_path(), callback=pane.focus)

def _get_volumes_path():
	if PLATFORM == 'Mac':
		return '/Volumes'
	elif PLATFORM == 'Windows':
		# Go to "My Computer":
		return ''
	elif PLATFORM == 'Linux':
		if isdir('/media'):
			contents = listdir('/media')
			user_name = _get_user()
			if contents == [user_name]:
				return join('/media', user_name)
			else:
				return '/media'
		else:
			return '/mnt'
	else:
		raise NotImplementedError(PLATFORM)

def _get_user():
	try:
		return getuser()
	except:
		return basename(expanduser('~'))

class GoTo(_CorePaneCommand):
	def __call__(self):
		visited_paths = load_json('Visited Paths.json', default={})
		if not visited_paths:
			visited_paths.update({
				path: 0 for path in self._get_default_paths()
			})
		get_items = SuggestLocations(visited_paths)
		result = show_quicksearch(get_items, self._get_tab_completion)
		if result:
			text, item = result
			path = ''
			if item:
				path = expanduser(item.value)
			if not isdir(path):
				path = expanduser(text)
			if isdir(path):
				self.pane.set_path(path)
	def _get_default_paths(self):
		result = []
		home_dir = expanduser('~')
		for file_name in listdir(home_dir):
			file_path = join(home_dir, file_name)
			if isdir(file_path) and not _is_hidden(file_path):
				result.append(join('~', file_name))
		if PLATFORM == 'Windows':
			for candidate in (r'C:\Program Files', r'C:\Program Files (x86)'):
				if isdir(candidate):
					result.append(candidate)
		elif PLATFORM == 'Mac':
			result.append('/Volumes')
		elif PLATFORM == 'Linux':
			media_user = join('/media', _get_user())
			if exists(media_user):
				result.append(media_user)
			elif exists('/media'):
				result.append('/media')
			if exists('/mnt'):
				result.append('/mnt')
		return result
	def _get_tab_completion(self, item):
		result = item.value
		if not result.endswith(os.sep):
			result += os.sep
		return result

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
		new_path = unexpand_user(self.pane.get_path())
		visited_paths = \
			load_json('Visited Paths.json', default={}, save_on_quit=True)
		visited_paths[new_path] = visited_paths.get(new_path, 0) + 1

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

	def __init__(self, visited_paths, file_system=None):
		if file_system is None:
			# Encapsulating filesystem-related functionality in a separate field
			# allows us to use a different implementation for testing.
			file_system = FileSystem()
		self.visited_paths = visited_paths
		self.fs = file_system
	def __call__(self, query):
		possible_dirs = self._gather_dirs(query)
		items = self._filter_matching(possible_dirs, query)
		return list(self._remove_nonexistent(items))
	def _gather_dirs(self, query):
		sort_key = lambda path: (-self.visited_paths.get(path, 0), path.lower())
		path = normpath(self.fs.expanduser(query))
		if PLATFORM == 'Windows':
			# Windows completely ignores trailing spaces in directory names at
			# all times. Make our implementation reflect this:
			path = path.rstrip(' ')
		if path != '.' and self.fs.isdir(path) or self.fs.isdir(dirname(path)):
			result = OrderedSet()
			if self.fs.isdir(path):
				result.add(self._unexpand_user(path))
				dir_ = path
			else:
				dir_ = dirname(path)
			dir_items = []
			for name in self.fs.listdir(dir_):
				file_path = join(dir_, name)
				if self.fs.isdir(file_path):
					dir_items.append(join(self._unexpand_user(dir_), name))
			dir_items.sort(key=sort_key)
			result.update(dir_items)
			return result
		else:
			return sorted(self.visited_paths, key=sort_key)
	def _filter_matching(self, dirs, query):
		result = [[] for _ in self._MATCHERS]
		for dir_ in dirs:
			for i, matcher in enumerate(self._MATCHERS):
				match = matcher(dir_.lower(), query.lower())
				if match is not None:
					result[i].append(QuicksearchItem(dir_, highlight=match))
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
	def _unexpand_user(self, path):
		return unexpand_user(path, self.fs.expanduser)

class FileSystem:
	def isdir(self, path):
		return isdir(path)
	def expanduser(self, path):
		return expanduser(path)
	def listdir(self, path):
		try:
			return listdir(path)
		except PermissionError:
			if PLATFORM == 'Windows' and _is_documents_and_settings(path):
				# Python can' listdir("C:\Documents and Settings"). In fact, no
				# Windows program can. But "C:\{DaS}\<Username>" does work, and
				# displays "C:\Users\<Username>". For consistency, treat DaS
				# like a symlink to \Users:
				return listdir(splitdrive(path)[0] + r'\Users')
			raise

def _is_documents_and_settings(path):
	return splitdrive(normpath(path))[1].lower() == '\\documents and settings'

class CommandPalette(_CorePaneCommand):

	_MATCHERS = (contains_chars_after_separator(' '), contains_chars)

	_KEY_SYMBOLS_MAC = {
		'Cmd': '⌘', 'Alt': '⌥', 'Ctrl': '⌃', 'Shift': '⇧', 'Backspace': '⌫',
		'Up': '↑', 'Down': '↓', 'Left': '←', 'Right': '→', 'Enter': '↩'
	}

	def __call__(self):
		result = show_quicksearch(self._suggest_commands)
		if result:
			item = result[1]
			if item:
				self.pane.run_command(item.value)
	def _suggest_commands(self, query):
		result = [[] for _ in self._MATCHERS]
		for command in sorted(self.pane.get_commands(), key=len):
			command_title = command.capitalize().replace('_', ' ')
			for i, matcher in enumerate(self._MATCHERS):
				match = matcher(command_title.lower(), query.lower())
				if match is not None:
					hint = ', '.join(self._get_shortcuts_for_command(command))
					item = QuicksearchItem(command, command_title, match, hint)
					result[i].append(item)
					break
		return list(chain.from_iterable(result))
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

class Quit(DirectoryPaneCommand):
	def __call__(self):
		sys.exit(0)

class InstallLicenseKey(DirectoryPaneCommand):
	def __call__(self):
		license_key = join(self.pane.get_path(), 'User.json')
		if not exists(license_key):
			show_alert(
				'Could not find license key file "User.json" in the current '
				'directory %s.' % self.pane.get_path()
			)
			return
		destination_directory = join(DATA_DIRECTORY, 'Local')
		copy(license_key, destination_directory)
		show_alert(
			"Thank you! To complete the registration, please restart fman. You "
			"should no longer see the annoying popup when it starts."
		)

class ZenOfFman(DirectoryPaneCommand):
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
			"Development speed matters more than program size"
		)

class OpenDataDirectory(DirectoryPaneCommand):
	def __call__(self):
		self.pane.set_path(DATA_DIRECTORY)

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