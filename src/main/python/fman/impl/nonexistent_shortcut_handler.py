from os.path import dirname, basename, splitdrive
from fman import show_alert, YES, NO, run_application_command
from fman.fs import is_dir
from fman.impl.html_style import highlight
from fman.impl.util.qt import Key_Up
from fman.impl.util.system import is_mac
from PyQt5.QtCore import QEvent, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QDialog, QLabel, QVBoxLayout, QRadioButton, \
	QLineEdit, QDialogButtonBox, QCheckBox

class NonexistentShortcutHandler:

	_TAB_MESSAGE = \
		'The shortcut for switching between panes is %s. Unfortunately, it ' \
		'is not (yet) possible to change this behaviour. If it is important ' \
		'to you, please create an issue at ' \
		'<a href="https://fman.io/issues">https://fman.io/issues</a>.' \
		% highlight('Tab')
	_THANK_YOU_FOR_FEEDBACK_MESSAGE = \
		'Thank you for your feedback. We will take it into account for ' \
		'future versions of fman!'

	def __init__(self, main_window, settings, metrics):
		self._main_window = main_window
		self._settings = settings
		self._metrics = metrics
	def __call__(self, key_event, pane):
		self._metrics.track('UsedNonexistentShortcut', {
			'shortcut': str(key_event)
		})
		if key_event.matches('Left'):
			self._handle_key_left(pane)
		elif key_event.matches('Right'):
			self._handle_key_right(pane)
	def _handle_key_left(self, pane):
		dialog_id = 'NonExistentShortcutPromptLeft'
		if not self._should_show_suggestions(dialog_id):
			return
		title = 'The shortcut %s is not defined. ' \
				'What do you want to do?' % highlight('Arrow-Left')
		options = []
		is_right_pane = pane.window.get_panes().index(pane) > 0
		parent_directory = dirname(pane.get_path())
		if parent_directory != pane.get_path():
			dir_name = basename(parent_directory) \
					   or splitdrive(parent_directory)[0]\
					   or '/'
			options.append((
				'Go to parent directory',
				'Go to the parent directory ("%s")' % dir_name
			))
		file_under_cursor = pane.get_file_under_cursor()
		if is_right_pane and is_dir(file_under_cursor):
			options.append((
				'Open in left pane',
				'Open "%s" in the left pane' % basename(file_under_cursor)
			))
		prev_in_history = self._get_previous_folder_in_history(pane)
		if prev_in_history:
			options.append((
				'Go back',
				'Go back to the previous folder ("%s")' %
				basename(prev_in_history)
			))
		if is_right_pane:
			options.append(('Switch to left pane', 'Switch to the left pane'))
		choice = self._show_suggestions(dialog_id, title, options)
		if not choice:
			return
		if choice == 'Go to parent directory':
			self._offer_to_install_arrownavigation_plugin(
				'The normal shortcut for going to the parent directory '
				'is %s. ' % highlight('Backspace')
			)
		elif choice == 'Open in left pane':
			self._offer_to_customize_keybindings(
				'The normal shortcut for opening a directory in the left pane '
				'is %s. ' % highlight('Ctrl+Left')
			)
		elif choice == 'Move cursor up':
			self._offer_to_customize_keybindings(
				'The normal shortcut for moving the cursor up is %s. '
				% highlight('Arrow-Up')
			)
		elif choice == 'Go back':
			self._offer_to_customize_keybindings(
				'The normal shortcut for going back to the previous '
				'folder is %s. '
				% highlight(('Cmd' if is_mac() else 'Alt') + '+Left')
			)
		elif choice == 'Switch to left pane':
			show_alert(self._TAB_MESSAGE)
		else:
			assert choice == 'Other'
			show_alert(self._THANK_YOU_FOR_FEEDBACK_MESSAGE)
	def _handle_key_right(self, pane):
		dialog_id = 'NonExistentShortcutPromptRight'
		if not self._should_show_suggestions(dialog_id):
			return
		title = 'The shortcut %s is not defined. ' \
				'What do you want to do?' % highlight('Arrow-Right')
		options = []
		is_left_pane = pane.window.get_panes().index(pane) == 0
		file_under_cursor = pane.get_file_under_cursor()
		if is_dir(file_under_cursor):
			dir_name = basename(file_under_cursor)
			options.append((
				'Open directory', 'Open the directory "%s"' % dir_name
			))
			if is_left_pane:
				options.append((
					'Open in right pane',
					'Open "%s" in the right pane' % dir_name
				))
		next_in_history = self._get_next_folder_in_history(pane)
		if next_in_history:
			options.append((
				'Go forward',
				'Go forward in history (to "%s")' % basename(next_in_history)
			))
		if is_left_pane:
			options.append(('Switch to right pane','Switch to the right pane'))
		choice = self._show_suggestions(dialog_id, title, options)
		if not choice:
			return
		if choice == 'Open directory':
			self._offer_to_install_arrownavigation_plugin(
				'The normal shortcut for opening a directory is %s. '
				% highlight('Enter')
			)
		elif choice == 'Open in right pane':
			self._offer_to_customize_keybindings(
				'The normal shortcut for opening a directory in the right pane '
				'is %s. ' % highlight('Ctrl+Right')
			)
		elif choice == 'Move cursor down':
			self._offer_to_customize_keybindings(
				'The normal shortcut for moving the cursor down is %s. '
				% highlight('Arrow-Down')
			)
		elif choice == 'Go forward':
			self._offer_to_customize_keybindings(
				'The normal shortcut for going forward in history is %s. '
				% highlight(('Cmd' if is_mac() else 'Alt') + '+Right')
			)
		elif choice == 'Switch to right pane':
			show_alert(self._TAB_MESSAGE)
		else:
			assert choice == 'Other'
			show_alert(self._THANK_YOU_FOR_FEEDBACK_MESSAGE)
	def _should_show_suggestions(self, dialog_id):
		return not self._settings.get(dialog_id, {}).get('suppress', False)
	def _get_previous_folder_in_history(self, pane):
		history = self._get_history(pane)
		if history._curr_path > 0:
			return history._paths[history._curr_path - 1]
	def _get_next_folder_in_history(self, pane):
		history = self._get_history(pane)
		if history._curr_path + 1 < len(history._paths):
			return history._paths[history._curr_path + 1]
	def _get_history(self, pane):
		from core.commands import HistoryListener
		return HistoryListener.INSTANCES[pane]._history
	def _show_suggestions(self, dialog_id, title, options):
		dialog = NonexistentShortcutDialog(self._main_window, title, options)
		result = self._main_window.exec_dialog(dialog)
		if result == QDialog.Rejected:
			return None
		if dialog.checked_dont_ask_again():
			self._settings.setdefault(dialog_id, {})['suppress'] = True
			try:
				self._settings.flush()
			except OSError:
				pass
		choice = dialog.get_choice()
		self._metrics.track('AnsweredNonexistentShortcutDialog', {
			'choice': choice,
			'text': dialog.get_other_text()
		})
		return choice
	def _offer_to_customize_keybindings(self, pretext):
		choice = show_alert(
			pretext +
			'Would you like to see how you can customize fman\'s '
			'key bindings to change it?',
			YES | NO, YES
		)
		if choice & YES:
			self._open_url(
				'https://fman.io/docs/custom-shortcuts?s=f'
			)
	def _offer_to_install_arrownavigation_plugin(self, pretext):
		choice = show_alert(
			pretext +
			'There is a plugin that lets you use %s to go up, %s to open '
			'directories. Do you want to install it?'
			% (highlight('Left'), highlight('Right')),
			YES | NO, YES
		)
		if choice & YES:
			run_application_command('install_plugin', {
				'github_repo': 'mherrmann/ArrowNavigation'
			})
	def _open_url(self, url):
		QDesktopServices.openUrl(QUrl(url))

class NonexistentShortcutDialog(QDialog):
	def __init__(self, parent, title, options):
		super().__init__(parent)
		self._options = options + [('Other', 'Other (please specify):')]
		self._choice = self._checked_dont_ask_again = self._other_text = None

		layout = QVBoxLayout(self)

		title_label = QLabel(title, self)
		title_label.setWordWrap(True)
		layout.addWidget(title_label)

		self._radio_buttons = \
			[QRadioButton(option[1]) for option in self._options]
		for radio_button in self._radio_buttons:
			layout.addWidget(radio_button)
		self._radio_buttons[0].setChecked(True)

		self._other_text_edit = QLineEdit()
		self._other_text_edit.installEventFilter(self)
		self._other_radio_button = self._radio_buttons[-1]
		self._other_radio_button.setFocusProxy(self._other_text_edit)
		layout.addWidget(self._other_text_edit)

		self._dont_ask_again = QCheckBox("Don't &ask again")
		layout.addWidget(self._dont_ask_again)

		buttons = \
			QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
		buttons.accepted.connect(self.accept)
		buttons.rejected.connect(self.reject)
		layout.addWidget(buttons)

		self.setLayout(layout)
	def eventFilter(self, object, event):
		if object == self._other_text_edit:
			if event.type() == QEvent.FocusIn:
				self._other_radio_button.setChecked(True)
			elif event.type() == QEvent.KeyPress and event.key() == Key_Up:
				btn_before_other = self._radio_buttons[-2]
				btn_before_other.setChecked(True)
				btn_before_other.setFocus()
		return False
	def accept(self):
		choice_index = \
			[rb.isChecked() for rb in self._radio_buttons].index(True)
		self._choice = self._options[choice_index][0]
		self._other_text = self._other_text_edit.text()
		self._checked_dont_ask_again = self._dont_ask_again.isChecked()
		super().accept()
	def get_choice(self):
		return self._choice
	def get_other_text(self):
		return self._other_text
	def checked_dont_ask_again(self):
		return self._checked_dont_ask_again