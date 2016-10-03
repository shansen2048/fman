from fileoperations import CopyFiles, MoveFiles
from fman import DirectoryPaneCommand, YES, NO, OK, CANCEL, load_json, \
	platform, write_json
from hiddenfiles import is_hidden
from os import mkdir
from os.path import join, pardir, isfile, exists, splitdrive, basename, \
	normpath, isdir, split
from os_ import open_file_with_app, open_terminal_in_directory, \
	open_native_file_manager
from threading import Thread
from trash import move_to_trash

import clipboard
import sys

class CorePaneCommand(DirectoryPaneCommand):
	def toggle_current(self):
		self.pane.toggle_selection(self.pane.get_file_under_cursor())

class DoNothing(CorePaneCommand):
	def __call__(self):
		return False

class MoveCursorDown(CorePaneCommand):
	def __call__(self, toggle_current=False):
		if toggle_current:
			self.toggle_current()
		self.pane.move_cursor_down()

class MoveCursorUp(CorePaneCommand):
	def __call__(self, toggle_current=False):
		if toggle_current:
			self.toggle_current()
		self.pane.move_cursor_up()

class MoveCursorHome(CorePaneCommand):
	def __call__(self, toggle_current=False):
		self.pane.move_cursor_home(toggle_current)

class MoveCursorEnd(CorePaneCommand):
	def __call__(self, toggle_current=False):
		self.pane.move_cursor_end(toggle_current)

class MoveCursorPageUp(CorePaneCommand):
	def __call__(self, toggle_current=False):
		self.pane.move_cursor_page_up(toggle_current)
		self.pane.move_cursor_up()

class MoveCursorPageDown(CorePaneCommand):
	def __call__(self, toggle_current=False):
		self.pane.move_cursor_page_down(toggle_current)
		self.pane.move_cursor_down()

class ToggleCurrent(CorePaneCommand):
	def __call__(self):
		self.toggle_current()

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
		parent_dir = join(current_dir, pardir)
		callback = lambda: self.pane.place_cursor_at(current_dir)
		self.pane.set_path(parent_dir, callback)

class Open(CorePaneCommand):
	def __call__(self):
		self.pane.open(self.pane.get_file_under_cursor())

class OpenWithEditor(CorePaneCommand):
	_PLATFORM_APPLICATIONS_FILTER = {
		'Mac': 'Applications (*.app)',
		'Windows': 'Applications (*.exe)',
		'Linux': 'Applications (*)'
	}
	def __call__(self):
		file_under_cursor = self.pane.get_file_under_cursor()
		if not isfile(file_under_cursor):
			self.ui.show_alert("No file is selected!")
		else:
			settings = load_json('Core Settings.json') or {}
			editor = settings.get('editor', None)
			if not editor:
				choice = self.ui.show_alert(
					'Editor is currently not configured. Please pick one.',
					OK | CANCEL, OK
				)
				if choice & OK:
					result = self.ui.show_file_open_dialog(
						'Pick an Editor', self._get_applications_directory(),
						self._PLATFORM_APPLICATIONS_FILTER[platform()]
					)
					if result:
						editor = result[0]
						settings['editor'] = editor
						write_json(settings, 'Core Settings.json')
			if editor:
				open_file_with_app(file_under_cursor, editor)
	def _get_applications_directory(self):
		if platform() == 'Mac':
			return '/Applications'
		elif platform() == 'Windows':
			result = r'c:\Program Files'
			if not exists(result):
				result = splitdrive(sys.executable)[0] + '\\'
			return result
		elif platform() == 'Linux':
			return '/usr/bin'
		raise NotImplementedError(platform())

class TreeCommand(CorePaneCommand):
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
		self.pane.rename(self.pane.get_file_under_cursor())

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
		self.pane.add_filter(self.filter)
		self.show_hidden_files = True
	def filter(self, file_path):
		if self.show_hidden_files:
			return True
		return not is_hidden(file_path)
	def __call__(self):
		self.show_hidden_files = not self.show_hidden_files
		self.pane.invalidate_filter()