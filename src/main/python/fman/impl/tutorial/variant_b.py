from fman.impl.tutorial import Tutorial, TutorialStep
from fman.impl.util import is_below_dir
from fman.impl.util.qt import run_in_main_thread
from fman.impl.util.system import is_mac, is_windows
from os.path import expanduser, relpath, realpath, dirname, splitdrive, basename
from PyQt5.QtWidgets import QFileDialog
from time import time

class TutorialVariantB(Tutorial):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._target_directory = self._source_directory = \
			self._start_time = self._time_taken = None
	def _get_steps(self):
		cmd_p = '⌘P' if is_mac() else 'Ctrl+P'
		if is_windows():
			native_fm = 'Explorer'
		elif is_mac():
			native_fm = 'Finder'
		else:
			native_fm = 'your native file manager'
		if is_mac():
			delete_key = '⌘+⌫'
		else:
			delete_key = 'Delete'
		cmd_shift_p = 'Cmd+Shift+P' if is_mac() else 'Ctrl+Shift+P'
		return [
			TutorialStep(
				'Welcome to fman!',
				[
					"Would you like to take a quick tour of the most useful "
					"features? It takes less than five minutes and lets you "
					"hit the ground running."
				],
				buttons=[('No', self.reject), ('Yes', self._next_step)]
			),
			TutorialStep(
				'Awesome!',
				[
					'We need an example. Please click the button below to '
					'select a directory. It should be a folder you use often. '
					'Also, it should be a little \"nested\" so you have to '
					'click through a few directories to get to it.'
				],
				buttons=[('Select a folder', self._pick_folder)]
			),
			TutorialStep(
				'', [
					"Cool. Here's a little challenge: How quickly can you "
					"navigate to *%s*?",
					"You can use the mouse, or the arrow keys followed by "
					"*Enter*. To jump to a directory, type the first few "
					"characters of its name. If you want to go up, "
					"press *Backspace*."
				],
				{
					'on': {
						'path_changed': self._check_target
					}
				}
			),
			TutorialStep(
				"",
				[
					"Great. That took you *%.2f* seconds. Let's see if we can "
					"make it faster!",
					"Click *Reset* to take you back to the directory you "
					"started from."
				],
				buttons=[('Reset', self._reset)]
			),
			TutorialStep(
				"",
				[
					"We will now use a feature that makes fman unique among "
					"file managers: It's called *GoTo*. Press *%s* to launch "
					"it!" % cmd_p
				],
				{
					'before': {
						'GoTo': self._after_quicksearch_shown(self._before_goto)
					}
				}
			),
			TutorialStep(
				'',
				[
					"GoTo lets you quickly jump to directories.",
					"Start typing *%s* into the dialog. fman will suggest "
					"your directory. Press *Enter* to open it."
				],
				{
					'after': {
						'GoTo': self._after_goto
					}
				}
			),
			TutorialStep(
				'',
				[
					"Well done! Did you see how quick that was?<br/>"
					"Let's do that again. Click *Reset* to continue."
				],
				buttons=[('Reset', self._reset_2)]
			),
			TutorialStep(
				'',
				[
					"We will now try to beat your previous time. Remember, you "
					"need to perform these steps:",
					"* Press *%s*" % cmd_p,
					"* Type *%s* into GoTo",
					"* Press *Enter*",
					"Ready? Just start!"
				],
				{
					'before': {
						'GoTo': self._after_quicksearch_shown(
							self._before_goto_2
						)
					},
					'after': {
						'GoTo': self._after_goto_2
					}
				}
			),
			TutorialStep(
				'',
				[
					"Not bad! This time it took you *%.2f* seconds. That's "
					"still a little longer than your previous time of *%.2f* "
					"seconds. Would you like to try again?"
				],
				buttons=[
					('No, continue', self._give_up),
					('Yes, try again', self._try_again)
				]
			),
			TutorialStep(
				'',
				[
					"Great work! You opened the directory in *%.2f* seconds. "
					"That beats your previous time of *%.2f*. Well done!",
					"The next time you navigate to *%s*, ask yourself: Isn't "
					"it tedious to click through these directory trees all the "
					"time? fman is the answer."
				],
				buttons=[
					('Continue', self._next_step)
				]
			),
			TutorialStep(
				'',
				[
					"A limitation of *GoTo* is that it sometimes doesn't "
					"suggest directories which you have not yet visited. If "
					"that happens, simply navigate to the folder manually once "
					"and you'll be good to go."
				],
				buttons=[
					('Okay!', self._next_step)
				]
			),
			TutorialStep(
				'',
				[
					"fman is young and still lacks many features. To work "
					"around this, you can always open %s. Please press *F10* "
					"to see this in action." % native_fm
				],
				{
					'after': {
						'OpenNativeFileManager': self._next_step
					}
				}
			),
			TutorialStep(
				'',
				[
					"Well done! fman opened %s in your current directory."
					% native_fm,
					"It's finally time to explain why fman always displays two "
					"directories. Apps like this are called *dual-pane file "
					"managers*. Have you used one before?"
				],
				buttons=[
					('No', self._next_step), ('Yes', self._skip_steps(3))
				]
			),
			TutorialStep(
				'',
				[
					"Dual-pane file managers make it especially easy to copy "
					"and move files: You simply open the directory you want to "
					"copy from on one side, and the directory you want to copy "
					"to on the other. Then, you press a key combination to "
					"perform the copy. Do you want to see a brief example?"
				],
				buttons=[
					('No', self._skip_steps(1)), ('Yes', self._next_step)
				]
			),
			TutorialStep(
				'',
				[
					"Okay! Press *Tab* to move from one side to the other. "
					"This lets you navigate to the source and target "
					"directories. Then, select the file you want to copy and "
					"press *F5*. fman will ask you for confirmation. To delete "
					"the file afterwards, press *%s*." % delete_key
				],
				buttons=[('Continue', self._skip_steps(1))]
			),
			TutorialStep(
				'',
				[
					"No problem. In that case, all you need to know for now is "
					"that *Tab* lets you switch between the left and the right "
					"side."
				],
				buttons=[('Continue', self._next_step)]
			),
			TutorialStep(
				'',
				[
					"Dual-pane file managers rely heavily on keyboard "
					"shortcuts. But how do you remember them?",
					"fman's answer to this question is a searchable list of "
					"features. It's called the *Command Palette*. Please press "
					"*%s* to launch it." % cmd_shift_p
				],
				{
					'before': {
						'CommandPalette':
							self._after_quicksearch_shown(self._next_step)
					}
				}
			),
			TutorialStep(
				'',
				[
					"Well done! Note how the Command Palette shows fman's "
					"features as well as the shortcut for each command.",
					"Say you want to select all files, but don't know how. "
					"Type *select* into the Command Palette. It will suggest "
					"*Select all*. Confirm with *Enter*."
				],
				{
					'after': {
						'SelectAll': self._next_step
					}
				}
			),
			TutorialStep(
				'',
				[
					"Perfect! The files were selected. Here's a little "
					"challenge for you: _De_select the files!",
					"Hint: The shortcut for the Command Palette is *%s*."
					% cmd_shift_p
				],
				{
					'after': {
						'Deselect': self._next_step
					}
				}
			),
			TutorialStep(
				'Great Work!',
				[
					"You have completed the tutorial. Remember:",
					"* *%s* lets you go to any _P_ath." % cmd_p,
					"* *%s* opens the Command _P_alette." % cmd_shift_p,
					"* fman is best used with the keyboard.",
					"The Command Palette lets you look up all other "
					"features, so that's all you need to know.",
					"Have fun with fman! :-)"
				],
				buttons=[('Close', self.complete)]
			)
		]
	@run_in_main_thread
	def _pick_folder(self):
		dir_path = QFileDialog.getExistingDirectory(
			self._main_window, 'Pick a folder', expanduser('~'),
			QFileDialog.ShowDirsOnly
		)
		if dir_path:
			self._target_directory = dir_path
			self._source_directory = self._get_source_directory(dir_path)
			self._pane.set_path(self._source_directory)
			self._format_next_step_paragraph(dir_path)
			self._next_step()
	def _get_source_directory(self, target_dir):
		current = self._pane.get_path()
		if self._get_num_directory_lvls_between(target_dir, current) >= 3:
			return current
		home = expanduser('~')
		if is_below_dir(target_dir, home):
			if self._get_num_directory_lvls_between(target_dir, home) >= 3:
				return home
		return splitdrive(target_dir)[0] or '/'
	def _get_num_directory_lvls_between(self, subdir, pardir):
		result = 0
		rel = relpath(realpath(subdir), realpath(pardir))
		while rel:
			result += 1
			rel = dirname(rel)
		return result
	def _format_next_step_paragraph(self, *values):
		step_paras = self._steps[self._curr_step_index + 1]._paragraphs
		for i, value in enumerate(values):
			step_paras[i] %= value
	def _check_target(self):
		current_path = self._pane.get_path()
		if self._start_time is None and current_path != self._source_directory:
			self._start_time = time()
		elif current_path == self._target_directory:
			self._time_taken = time() - self._start_time
			self._format_next_step_paragraph(self._time_taken)
			self._next_step()
	def _reset(self):
		self._pane.set_path(self._source_directory)
		self._next_step()
	def _before_goto(self):
		goto_dir = basename(self._target_directory)
		self._format_next_step_paragraph((), goto_dir)
		self._next_step()
	def _after_goto(self):
		path = self._pane.get_path()
		if path == self._target_directory:
			self._next_step()
	def _reset_2(self):
		goto_dir = basename(self._target_directory)
		self._format_next_step_paragraph((), (), goto_dir, (), ())
		self._start_time = None
		self._reset()
	def _before_goto_2(self):
		if self._start_time is None:
			self._start_time = time()
	def _after_goto_2(self):
		path = self._pane.get_path()
		if path == self._target_directory:
			time_taken = time() - self._start_time
			if time_taken < self._time_taken:
				# Skip the "try again" step:
				self._curr_step_index += 1
				goto_dir = basename(self._target_directory)
				self._format_next_step_paragraph(
					(time_taken, self._time_taken), goto_dir
				)
			else:
				self._format_next_step_paragraph((time_taken, self._time_taken))
			self._next_step()
	def _try_again(self):
		self._start_time = None
		self._previous_step()
	def _give_up(self):
		self._curr_step_index += 1
		self._next_step()
	def _skip_steps(self, num_steps):
		return lambda: self._next_step(num_steps + 1)