from fman.impl.fileoperations import CopyFiles
from fman.util.qt import Key_Down, Key_Up, Key_Home, Key_End, Key_PageDown, \
	Key_PageUp, Key_Space, Key_Insert, ShiftModifier, Key_Backspace, \
	Key_Enter, Key_Return, Key_F6, Key_F7, Key_F8, Key_Delete, Key_F5, Key_F4, \
	Key_F11
from fman.util.system import is_osx
from os import rename
from os.path import abspath, join, pardir, dirname
from PyQt5.QtCore import QItemSelectionModel as QISM
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QInputDialog, QLineEdit, QMessageBox
from threading import Thread

class DirectoryPaneController:
	def __init__(self, os_, settings, app, gui_thread):
		self.os = os_
		self.settings = settings
		self.app = app
		self.gui_thread = gui_thread
		self.left_pane = self.right_pane = None
	def key_pressed_in_file_view(self, view, event):
		source = lambda: view.parentWidget()
		target = lambda: \
			self.left_pane if source() is self.right_pane else self.right_pane
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
			parent_dir = abspath(join(current_dir, pardir))
			callback = lambda: source().place_cursor_at(current_dir)
			source().set_path(parent_dir, callback)
		elif event.key() in (Key_Enter, Key_Return):
			view.activated.emit(view.currentIndex())
		elif event.key() == Key_F4:
			editor = self.settings['editor']
			if not editor:
				editor = self.os.prompt_user_to_pick_application(
					'Please pick an editor.'
				)
			if editor:
				self.os.open(*self._get_selected_files(view), with_app=editor)
				self.settings['editor'] = editor
		elif event.key() == Key_F5:
			to_copy = self._get_selected_files(view)
			dest_dir = target().get_path()
			Thread(target=CopyFiles(self.gui_thread, to_copy, dest_dir)).start()
		elif shift and event.key() == Key_F6:
			view.edit(view.currentIndex())
		elif event.key() == Key_F7:
			name, ok = QInputDialog.getText(
				source(), "fman", "New folder (directory)",
				QLineEdit.Normal, ""
			)
			if ok and name:
				model = view.model()
				pane = source()
				root_index = model.mapToSource(pane._root_index)
				model.sourceModel().mkdir(root_index, name)
				pane.place_cursor_at(join(pane.get_path(), name))
		elif event.key() in (Key_F8, Key_Delete):
			message_box = QMessageBox()
			to_delete = self._get_selected_files(view)
			if len(to_delete) > 1:
				description = 'these %d items' % len(to_delete)
			else:
				description = to_delete[0]
			message_box.setText(
				"Do you really want to move %s to the recycle bin?" %
				description
			)
			message_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
			message_box.setDefaultButton(QMessageBox.Yes)
			choice = message_box.exec()
			if choice & QMessageBox.Yes:
				self.os.move_to_trash(*to_delete)
		elif event.key() == Key_F11:
			to_copy = '\n'.join(self._get_selected_files(view))
			self.app.clipboard().setText(to_copy)
		elif event == QKeySequence.SelectAll:
			view.selectAll()
		else:
			event.ignore()
			result = False
		return result
	def activated(self, model, file_view, index):
		file_path = model.filePath(index)
		if model.isDir(index):
			file_view.clearSelection()
			file_view.parentWidget().set_path(file_path)
		else:
			self.os.open(file_path)
	def file_renamed(self, pane, model, index, new_name):
		if not new_name:
			return
		src = model.filePath(index)
		dest = join(dirname(src), new_name)
		rename(src, dest)
		pane.place_cursor_at(dest)
	def _get_selected_files(self, view):
		indexes = \
			view.selectionModel().selectedIndexes() or [view.currentIndex()]
		model = view.model()
		return [
			model.sourceModel().filePath(model.mapToSource(index))
			for index in indexes
		]
	def _get_selection_flag(self, view, shift_pressed):
		if shift_pressed:
			if view.selectionModel().isSelected(view.currentIndex()):
				return QISM.Deselect | QISM.Current
			else:
				return QISM.Select | QISM.Current
		else:
			return QISM.NoUpdate