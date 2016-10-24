from core import clipboard
from core.fileoperations import CopyFiles, MoveFiles
from core.os_ import open_file_with_app, open_terminal_in_directory, \
	open_native_file_manager
from core.trash import move_to_trash
from fman import DirectoryPaneCommand, YES, NO, OK, CANCEL, load_json, \
	PLATFORM, DirectoryPaneListener, show_quicksearch, show_prompt, save_json
from itertools import chain
from ordered_set import OrderedSet
from os import mkdir, rename, listdir
from os.path import join, isfile, exists, splitdrive, basename, normpath, \
	isdir, split, dirname, realpath, expanduser
from PyQt5.QtCore import QFileInfo, QUrl
from PyQt5.QtGui import QDesktopServices
from threading import Thread

import fman
import os
import sys

class CorePaneCommand(DirectoryPaneCommand):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		# The field `ui` is useful for automated tests: Tests can overwrite it
		# with a stub implementation to run without an actual GUI.
		self.ui = fman
	def toggle_selection(self):
		self.pane.toggle_selection(self.pane.get_file_under_cursor())

class MoveCursorDown(CorePaneCommand):
	def __call__(self, toggle_selection=False):
		if toggle_selection:
			self.toggle_selection()
		self.pane.move_cursor_down()

class MoveCursorUp(CorePaneCommand):
	def __call__(self, toggle_selection=False):
		if toggle_selection:
			self.toggle_selection()
		self.pane.move_cursor_up()

class MoveCursorHome(CorePaneCommand):
	def __call__(self, toggle_selection=False):
		self.pane.move_cursor_home(toggle_selection)

class MoveCursorEnd(CorePaneCommand):
	def __call__(self, toggle_selection=False):
		self.pane.move_cursor_end(toggle_selection)

class MoveCursorPageUp(CorePaneCommand):
	def __call__(self, toggle_selection=False):
		self.pane.move_cursor_page_up(toggle_selection)
		self.pane.move_cursor_up()

class MoveCursorPageDown(CorePaneCommand):
	def __call__(self, toggle_selection=False):
		self.pane.move_cursor_page_down(toggle_selection)
		self.pane.move_cursor_down()

class ToggleSelection(CorePaneCommand):
	def __call__(self):
		self.toggle_selection()

class MoveToTrash(CorePaneCommand):
	def __call__(self):
		to_delete = self.get_chosen_files()
		if len(to_delete) > 1:
			description = 'these %d items' % len(to_delete)
		else:
			description = to_delete[0]
		choice = self.ui.show_alert(
			"Do you really want to move %s to the recycle bin?" %
			description, YES | NO, YES
		)
		if choice & YES:
			move_to_trash(*to_delete)

class GoUp(CorePaneCommand):
	def __call__(self):
		current_dir = self.pane.get_path()
		parent_dir = dirname(current_dir)
		callback = lambda: self.pane.place_cursor_at(current_dir)
		self.pane.set_path(parent_dir, callback)

class Open(CorePaneCommand):
	def __call__(self):
		_open(self.pane, self.pane.get_file_under_cursor())

class OpenListener(DirectoryPaneListener):
	def on_doubleclicked(self, file_path):
		_open(self.pane, file_path)

def _open(pane, file_path):
	if isdir(file_path):
		pane.set_path(realpath(file_path))
	else:
		QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))

class OpenWithEditor(CorePaneCommand):
	_PLATFORM_APPLICATIONS_FILTER = {
		'Mac': 'Applications (*.app)',
		'Windows': 'Applications (*.exe)',
		'Linux': 'Applications (*)'
	}
	def __call__(self, create_new=False):
		file_under_cursor = self.pane.get_file_under_cursor()
		file_to_edit = ''
		if create_new:
			if isfile(file_under_cursor):
				default_name = basename(file_under_cursor)
			else:
				default_name = ''
			file_name, ok = \
				show_prompt('Enter file name to create/edit:', default_name)
			if ok and file_name:
				file_to_edit = join(self.pane.get_path(), file_name)
				if not exists(file_to_edit):
					open(file_to_edit, 'w').close()
				self.pane.place_cursor_at(file_to_edit)
		else:
			if isfile(file_under_cursor):
				file_to_edit = file_under_cursor
			else:
				self.ui.show_alert("No file is selected!")
		if isfile(file_to_edit):
			self._open_with_editor(file_to_edit)
	def _open_with_editor(self, file_path):
		settings = load_json('Core Settings.json', default={})
		editor = settings.get('editor', None)
		if not editor:
			choice = self.ui.show_alert(
				'Editor is currently not configured. Please pick one.',
				OK | CANCEL, OK
			)
			if choice & OK:
				result = self.ui.show_file_open_dialog(
					'Pick an Editor', self._get_applications_directory(),
					self._PLATFORM_APPLICATIONS_FILTER[PLATFORM]
				)
				if result:
					editor = result[0]
					settings['editor'] = editor
					save_json('Core Settings.json')
		if editor:
			open_file_with_app(file_path, editor)
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

class TreeCommand(CorePaneCommand):
	@property
	def other_pane(self):
		panes = self.pane.window.get_panes()
		return panes[(panes.index(self.pane) + 1) % len(panes)]
	def _confirm_tree_operation(self, files, dest_dir, descr_verb):
		if len(files) == 1:
			file_, = files
			dest_name = basename(file_) if isfile(file_) else ''
			files_descr = '"%s"' % basename(file_)
		else:
			dest_name = ''
			files_descr = '%d files' % len(files)
		message = '%s %s to' % (descr_verb.capitalize(), files_descr)
		dest = normpath(join(dest_dir, dest_name))
		dest, ok = self.ui.show_prompt(message, dest)
		if ok:
			if exists(dest):
				if isdir(dest):
					return dest, None
				else:
					if len(files) == 1:
						return split(dest)
					else:
						self.ui.show_alert(
							'You cannot %s multiple files to a single file!' %
							descr_verb
						)
			else:
				if len(files) == 1:
					return split(dest)
				else:
					choice = self.ui.show_alert(
						'%s does not exist. Do you want to create it '
						'as a directory and %s the files there?' %
						(dest, descr_verb), YES | NO, YES
					)
					if choice & YES:
						return dest, None
	def _copy(self, files, dest_dir, src_dir=None, dest_name=None):
		copy = CopyFiles(self.ui, files, dest_dir, src_dir, dest_name)
		Thread(target=copy).start()
	def _move(self, files, dest_dir, src_dir=None, dest_name=None):
		move = MoveFiles(self.ui, files, dest_dir, src_dir, dest_name)
		Thread(target=move).start()

class Copy(TreeCommand):
	def __call__(self):
		files = self.get_chosen_files()
		dest_dir = self.other_pane.get_path()
		proceed = self._confirm_tree_operation(files, dest_dir, 'copy')
		if proceed:
			dest_dir, dest_name = proceed
			src_dir = self.pane.get_path()
			self._copy(files, dest_dir, src_dir, dest_name)

class Move(TreeCommand):
	def __call__(self):
		files = self.get_chosen_files()
		dest_dir = self.other_pane.get_path()
		proceed = self._confirm_tree_operation(files, dest_dir, 'move')
		if proceed:
			dest_dir, dest_name = proceed
			src_dir = self.pane.get_path()
			self._move(files, dest_dir, src_dir, dest_name)

class Rename(CorePaneCommand):
	def __call__(self):
		self.pane.edit_name(self.pane.get_file_under_cursor())

class RenameListener(DirectoryPaneListener):
	def on_name_edited(self, file_path, new_name):
		if not new_name:
			return
		new_path = join(dirname(file_path), new_name)
		rename(file_path, new_path)
		self.pane.place_cursor_at(new_path)

class CreateDirectory(CorePaneCommand):
	def __call__(self):
		name, ok = self.ui.show_prompt("New folder (directory)")
		if ok and name:
			dir_path = join(self.pane.get_path(), name)
			mkdir(dir_path)
			self.pane.place_cursor_at(dir_path)

class OpenTerminal(CorePaneCommand):
	def __call__(self):
		open_terminal_in_directory(self.pane.get_path())

class OpenNativeFileManager(CorePaneCommand):
	def __call__(self):
		open_native_file_manager(self.pane.get_path())

class CopyPathsToClipboard(CorePaneCommand):
	def __call__(self):
		files = '\n'.join(self.get_chosen_files())
		clipboard.clear()
		clipboard.set_text(files)

class CopyToClipboard(CorePaneCommand):
	def __call__(self):
		clipboard.copy_files(self.get_chosen_files())

class Cut(CorePaneCommand):
	def __call__(self):
		clipboard.cut_files(self.get_chosen_files())

class Paste(TreeCommand):
	def __call__(self):
		files = clipboard.get_files()
		if clipboard.files_were_cut():
			self._move(files, self.pane.get_path())
			# The file has been cut; Clear the clipboard so the user doesn't
			# get an error when he accidentally pastes again:
			clipboard.clear()
		else:
			self._copy(files, self.pane.get_path())

class PasteCut(TreeCommand):
	def __call__(self):
		files = clipboard.get_files()
		self._move(files, self.pane.get_path())

class SelectAll(CorePaneCommand):
	def __call__(self):
		self.pane.select_all()

class ToggleHiddenFiles(CorePaneCommand):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.pane.add_filter(self.should_display)
		self.show_hidden_files = False
	def should_display(self, file_path):
		if self.show_hidden_files:
			return True
		if PLATFORM == 'Mac' and file_path == '/Volumes':
			return True
		return not _is_hidden(file_path)
	def __call__(self):
		self.show_hidden_files = not self.show_hidden_files
		self.pane.invalidate_filters()

def _is_hidden(file_path):
	return QFileInfo(file_path).isHidden()

class OpenInPaneCommand(CorePaneCommand):
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

class OpenInRightPane(OpenInPaneCommand):
	def get_source_pane(self, this_pane, num_panes):
		if this_pane == num_panes - 1:
			return this_pane - 1
		return this_pane
	def get_destination_pane(self, this_pane, num_panes):
		return min(this_pane + 1, num_panes - 1)

class OpenInLeftPane(OpenInPaneCommand):
	def get_source_pane(self, this_pane, num_panes):
		if this_pane > 0:
			return this_pane
		return 1
	def get_destination_pane(self, this_pane, num_panes):
		return max(this_pane - 1, 0)

class OpenDrives(CorePaneCommand):
	def __call__(self):
		if PLATFORM == 'Mac':
			self.pane.set_path('/Volumes')
		elif PLATFORM == 'Windows':
			# Go to "My Computer":
			self.pane.set_path('')
		raise NotImplementedError(PLATFORM)

class GoTo(CorePaneCommand):
	def __call__(self):
		visited_paths = load_json('Visited Paths.json', default={})
		if not visited_paths:
			visited_paths.update({
				path: 0 for path in self._get_default_paths()
			})
		get_suggestions = SuggestLocations(visited_paths)
		def get_tab_completion(suggestion):
			result = suggestion[0]
			if not result.endswith(os.sep):
				result += os.sep
			return result
		result = show_quicksearch(get_suggestions, get_tab_completion)
		if result:
			text, suggestion = result
			path = ''
			if suggestion:
				path = expanduser(suggestion[0])
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
	def __init__(self, visited_paths, file_system=None):
		if file_system is None:
			# Encapsulating filesystem-related functionality in a separate field
			# allows us to use a different implementation for testing.
			file_system = FileSystem()
		self.visited_paths = visited_paths
		self.fs = file_system
		self._matchers = [
			self._starts_with, self._name_starts_with,
			self._contains_upper_chars, self._contains_chars_ignorecase
		]
	def __call__(self, query):
		suggestions = self._gather_suggestions(query)
		return self._filter_suggestions(suggestions, query)
	def _gather_suggestions(self, query):
		sort_key = lambda path: (-self.visited_paths.get(path, 0), path.lower())
		path = self.fs.expanduser(query)
		if self.fs.isdir(path) or self.fs.isdir(dirname(path)):
			result = OrderedSet()
			if self.fs.isdir(path):
				if basename(path) != '.':
					# We check for '.' because we don't want to add "path/./" as
					# a suggestion for "path/.".
					result.add(self._unexpand_user(path))
				dir_ = path
			else:
				dir_ = dirname(path)
			dir_ = normpath(dir_)
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
	def _filter_suggestions(self, suggestions, query):
		matches = [[] for _ in self._matchers]
		for suggestion in suggestions:
			for i, matcher in enumerate(self._matchers):
				match = matcher(query, suggestion)
				if match:
					matches[i].append(match)
					break
		return list(chain.from_iterable(matches))
	def _unexpand_user(self, path):
		return unexpand_user(path, self.fs.expanduser)
	def _starts_with(self, query, suggestion):
		if suggestion.lower().startswith(query.lower()):
			return suggestion, list(range(len(query)))
	def _name_starts_with(self, query, suggestion):
		name = basename(suggestion.lower())
		if name.startswith(query.lower()):
			offset = len(suggestion) - len(name)
			return suggestion, [i + offset for i in range(len(query))]
	def _contains_upper_chars(self, query, suggestion):
		return self._contains_chars(query.upper(), suggestion, suggestion)
	def _contains_chars_ignorecase(self, query, suggestion):
		return self._contains_chars(
			query.lower(), suggestion.lower(), suggestion
		)
	def _contains_chars(self, query, suggestion, suggestion_to_return):
		try:
			return suggestion_to_return, self._find_chars(query, suggestion)
		except ValueError as not_found:
			pass
	def _find_chars(self, chars_to_find, in_string):
		indices = []
		i = 0
		for char in chars_to_find:
			i = in_string[i:].index(char) + i
			indices.append(i)
			i += 1
		return indices

class FileSystem:
	def isdir(self, path):
		return isdir(path)
	def expanduser(self, path):
		return expanduser(path)
	def listdir(self, path):
		return listdir(path)