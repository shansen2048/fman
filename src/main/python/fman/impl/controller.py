from fman.impl.fileoperations import CopyFiles, MoveFiles
from fman.impl.gui_operations import show_message_box
from fman.util.qt import Key_Down, Key_Up, Key_Home, Key_End, Key_PageDown, \
	Key_PageUp, Key_Space, Key_Insert, ShiftModifier, Key_Backspace, \
	Key_Enter, Key_Return, Key_F6, Key_F7, Key_F8, Key_Delete, Key_F5, Key_F4, \
	Key_F11, Key_F9, Yes, No, Ok, Cancel, Key_F10
from fman.util.system import is_osx
from os import rename
from os.path import join, pardir, dirname, basename, exists, isdir, split, \
	isfile, normpath
from PyQt5.QtCore import QItemSelectionModel as QISM, QUrl, QMimeData
from PyQt5.QtGui import QKeySequence, QDesktopServices
from PyQt5.QtWidgets import QInputDialog, QLineEdit, QFileDialog
from threading import Thread

class Controller:
	def __init__(self, main_window, os_, settings, clipboard, gui_thread):
		self.main_window = main_window
		self.os = os_
		self.settings = settings
		self.clipboard = clipboard
		self.gui_thread = gui_thread
	@property
	def left_pane(self):
		return self.main_window.left_pane
	@property
	def right_pane(self):
		return self.main_window.right_pane
	@property
	def status_bar(self):
		return self.main_window.status_bar
	def key_pressed_in_file_view(self, view, event):
		source = lambda: view.parentWidget()
		target = lambda: \
			self.left_pane if source() is self.right_pane else self.right_pane
		get_selected_files = lambda: self._get_selected_files(view)
		result = True
		shift = bool(event.modifiers() & ShiftModifier)
		if event.key() == Key_Down:
			if shift:
				view.toggle_current()
			view.move_cursor_down()
		elif event.key() == Key_Up:
			if shift:
				view.toggle_current()
			view.move_cursor_up()
		elif event.key() == Key_Home:
			view.move_cursor_home(self._get_selection_flag(view, shift))
		elif event.key() == Key_End:
			view.move_cursor_end(self._get_selection_flag(view, shift))
		elif event.key() == Key_PageUp:
			view.move_cursor_page_up(self._get_selection_flag(view, shift))
			view.move_cursor_up()
		elif event.key() == Key_PageDown:
			view.move_cursor_page_down(self._get_selection_flag(view, shift))
			view.move_cursor_down()
		elif event.key() == Key_Insert:
			view.toggle_current()
			view.move_cursor_down()
		elif event.key() == Key_Space:
			view.toggle_current()
			if is_osx():
				view.move_cursor_down()
		elif event.key() == Key_Backspace:
			current_dir = source().get_path()
			parent_dir = join(current_dir, pardir)
			callback = lambda: source().place_cursor_at(current_dir)
			source().set_path(parent_dir, callback)
		elif event.key() in (Key_Enter, Key_Return):
			view.activated.emit(view.currentIndex())
		elif event.key() == Key_F4:
			file_under_cursor = self._get_file_under_cursor(view)
			if not isfile(file_under_cursor):
				show_message_box("No file is selected!", Ok, Ok)
			else:
				editor = self.settings['editor']
				if not editor:
					choice = show_message_box(
						'Editor is currently not configured. Please pick one.',
						Ok | Cancel, Ok
					)
					if choice & Ok:
						result = QFileDialog.getOpenFileName(
							view, 'Pick an Editor',
							self.os.get_applications_directory(),
							self.os.get_applications_filter()
						)
						if result:
							editor = result[0]
				if editor:
					self.os.open_file_with_app(file_under_cursor, editor)
					self.settings['editor'] = editor
		elif event.key() == Key_F5:
			files = get_selected_files()
			dest_dir = target().get_path()
			proceed = self._confirm_tree_operation(files, dest_dir, 'copy')
			if proceed:
				dest_dir, dest_name = proceed
				src_dir = source().get_path()
				self._copy(files, dest_dir, src_dir, dest_name)
		elif event.key() == Key_F6:
			if shift:
				view.edit(view.currentIndex())
			else:
				files = get_selected_files()
				dest_dir = target().get_path()
				proceed = self._confirm_tree_operation(files, dest_dir, 'move')
				if proceed:
					dest_dir, dest_name = proceed
					src_dir = source().get_path()
					self._move(files, dest_dir, src_dir, dest_name)
		elif event.key() == Key_F7:
			name, ok = QInputDialog.getText(
				source(), "fman", "New folder (directory)",
				QLineEdit.Normal, ""
			)
			if ok and name:
				model = view.model()
				pane = source()
				root_index = model.mapToSource(view.rootIndex())
				model.sourceModel().mkdir(root_index, name)
				pane.place_cursor_at(join(pane.get_path(), name))
		elif event.key() in (Key_F8, Key_Delete):
			to_delete = get_selected_files()
			if len(to_delete) > 1:
				description = 'these %d items' % len(to_delete)
			else:
				description = to_delete[0]
			choice = show_message_box(
				"Do you really want to move %s to the recycle bin?" %
				description, Yes | No, Yes
			)
			if choice & Yes:
				self.os.move_to_trash(*to_delete)
		elif event.key() == Key_F9:
			self.os.open_terminal_in_directory(source().get_path())
		elif event.key() == Key_F10:
			self.os.open_native_file_manager(source().get_path())
		elif event.key() == Key_F11:
			files = '\n'.join(get_selected_files())
			self.clipboard.clear()
			self.clipboard.setText(files)
		elif event == QKeySequence.Copy:
			self.os.copy_files_to_clipboard(get_selected_files())
		elif event == QKeySequence.Cut:
			try:
				self.os.cut_files_to_clipboard(get_selected_files())
			except NotImplementedError:
				pass
		elif event == QKeySequence.Paste:
			files = self.os.get_files_in_clipboard()
			if self.os.files_in_clipboard_were_cut():
				self._move(files, source().get_path())
				# The file has been cut; Clear the clipboard so the user doesn't
				# get an error when he accidentally pastes again:
				self.clipboard.clear()
			else:
				self._copy(files, source().get_path())
		elif QKeySequence('Ctrl+Alt+V').matches(
			QKeySequence(event.modifiers() | event.key())
		):
			files = self.os.get_files_in_clipboard()
			self._move(files, source().get_path())
		elif event == QKeySequence.SelectAll:
			view.selectAll()
		else:
			event.ignore()
			result = False
		return result
	def _confirm_tree_operation(self, files, dest_dir, descr_verb):
		if len(files) == 1:
			file_, = files
			dest_name = basename(file_) if isfile(file_) else ''
			files_descr = '"%s"' % basename(file_)
		else:
			dest_name = ''
			files_descr = '%d files' % len(files)
		message = '%s %s to' % (descr_verb.capitalize(), files_descr)
		dest, ok = QInputDialog.getText(
			self.left_pane.parentWidget(), 'fman', message, QLineEdit.Normal,
			normpath(join(dest_dir, dest_name))
		)
		if ok:
			if exists(dest):
				if isdir(dest):
					return dest, None
				else:
					if len(files) == 1:
						return split(dest)
					else:
						show_message_box(
							'You cannot %s multiple files to a single file!' %
							descr_verb, Ok, Ok
						)
			else:
				if len(files) == 1:
					return split(dest)
				else:
					choice = show_message_box(
						'%s does not exist. Do you want to create it '
						'as a directory and %s the files there?' %
						(dest, descr_verb), Yes | No, Yes
					)
					if choice & Yes:
						return dest, None
	def _copy(self, files, dest_dir, src_dir=None, dest_name=None):
		copy = CopyFiles(
			self.gui_thread, self.status_bar, files, dest_dir, src_dir,
			dest_name
		)
		Thread(target=copy).start()
	def _move(self, files, dest_dir, src_dir=None, dest_name=None):
		move = MoveFiles(
			self.gui_thread, self.status_bar, files, dest_dir,
			src_dir, dest_name
		)
		Thread(target=move).start()
	def activated(self, model, file_view, index):
		file_path = model.filePath(index)
		if model.isDir(index):
			file_view.clearSelection()
			file_view.parentWidget().set_path(file_path)
		else:
			QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
	def file_renamed(self, pane, model, index, new_name):
		if not new_name:
			return
		src = model.filePath(index)
		dest = join(dirname(src), new_name)
		rename(src, dest)
		pane.place_cursor_at(dest)
	def _get_selected_files(self, view):
		indexes = view.selectionModel().selectedRows(column=0) \
				  or [view.currentIndex()]
		model = view.model()
		return [
			normpath(model.sourceModel().filePath(model.mapToSource(index)))
			for index in indexes
		]
	def _get_file_under_cursor(self, view):
		model = view.model()
		index = view.currentIndex()
		return model.sourceModel().filePath(model.mapToSource(index))
	def _get_selection_flag(self, view, shift_pressed):
		if shift_pressed:
			if view.selectionModel().isSelected(view.currentIndex()):
				return QISM.Deselect | QISM.Current
			else:
				return QISM.Select | QISM.Current
		else:
			return QISM.NoUpdate