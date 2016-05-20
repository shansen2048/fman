from fman.util.qt import Key_Down, Key_Up, Key_Home, Key_End, Key_PageDown, \
	Key_PageUp, Key_Space, Key_Insert, ShiftModifier, Key_Backspace, \
	Key_Enter, Key_Return, Key_F6, Key_F7, Key_F8, Key_Delete
from fman.util.system import is_osx
from os import rename
from os.path import abspath, join, pardir, dirname
from osxtrash import move_to_trash
from PyQt5.QtCore import QUrl, QItemSelectionModel as QISM
from PyQt5.QtGui import QKeySequence, QDesktopServices
from PyQt5.QtWidgets import QInputDialog, QLineEdit, QMessageBox

class DirectoryPaneController:
	def __init__(self, directory_pane):
		self.directory_pane = directory_pane
	def key_pressed_in_file_view(self, view, event):
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
			current_dir = self.directory_pane.get_path()
			parent_dir = abspath(join(current_dir, pardir))
			callback = lambda: self.directory_pane.place_cursor_at(current_dir)
			self.directory_pane.set_path(parent_dir, callback)
		elif event.key() in (Key_Enter, Key_Return):
			view.activated.emit(view.currentIndex())
		elif shift and event.key() == Key_F6:
			view.edit(view.currentIndex())
		elif event.key() == Key_F7:
			name, ok = QInputDialog.getText(
				self.directory_pane, "fman", "New folder (directory)",
				QLineEdit.Normal, ""
			)
			if name and ok:
				model = view.model()
				root_index = model.mapToSource(self.directory_pane._root_index)
				model.sourceModel().mkdir(root_index, name)
		elif event.key() in (Key_F8, Key_Delete):
			message_box = QMessageBox()
			indexes = \
				view.selectionModel().selectedIndexes() or [view.currentIndex()]
			model = view.model()
			to_delete = [
				model.sourceModel().filePath(model.mapToSource(index))
				for index in indexes
			]
			if len(indexes) > 1:
				description = 'these %d items' % len(to_delete)
			else:
				description = to_delete[0]
			message_box.setText(
				"Do you really want to move %s to the recycle bin?" % description
			)
			message_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
			message_box.setDefaultButton(QMessageBox.Yes)
			choice = message_box.exec()
			if choice & QMessageBox.Yes:
				move_to_trash(*to_delete)
		elif event == QKeySequence.SelectAll:
			view.selectAll()
		else:
			event.ignore()
			result = False
		return result
	def activated(self, model, view, index):
		file_path = model.filePath(index)
		if model.isDir(index):
			view.clearSelection()
			self.directory_pane.set_path(file_path)
		else:
			QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
	def file_renamed(self, model, index, new_name):
		if not new_name:
			return
		src = model.filePath(index)
		dest = join(dirname(src), new_name)
		rename(src, dest)
		self.directory_pane.place_cursor_at(dest)
	def _get_selection_flag(self, view, shift_pressed):
		if shift_pressed:
			if view.selectionModel().isSelected(view.currentIndex()):
				return QISM.Deselect | QISM.Current
			else:
				return QISM.Select | QISM.Current
		else:
			return QISM.NoUpdate