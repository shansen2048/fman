from fman.impl.tutorial import Tutorial, TutorialStep
from fman.util import is_below_dir
from fman.util.qt import run_in_main_thread
from fman.util.system import is_mac, is_windows
from os.path import expanduser, relpath, realpath, splitdrive, basename, \
	split, join, normpath
from PyQt5.QtWidgets import QFileDialog
from time import time

class TutorialVariantB(Tutorial):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._target_directory = self._source_directory = \
			self._start_time = self._time_taken = None
		self._encouragements = [
			e + '. ' for e in ('Great', 'Cool', 'Well done', 'Nice')
		]
		self._encouragement_index = 0
		self._last_step = ''
	def _get_steps(self):
		cmd_p = 'Cmd+P' if is_mac() else 'Ctrl+P'
		if is_windows():
			native_fm = 'Explorer'
		elif is_mac():
			native_fm = 'Finder'
		else:
			native_fm = 'your native file manager'
		if is_mac():
			delete_key = 'Cmd+Backspace'
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
			TutorialStep('', []),
			TutorialStep(
				"",
				[
					"Very well done! You opened your *%s* folder in *%.2f* "
					"seconds. Let's see if we can make it faster!",
					"Please click *Reset* to take you back to the directory you "
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
					"%s"
				],
				{
					'after': {
						'GoTo': self._after_goto
					}
				}
			),
			TutorialStep('', [], buttons=[('Continue', self._next_step)]),
			TutorialStep(
				'',
				[
					"A limitation of *GoTo* is that it sometimes doesn't "
					"suggest directories you haven't visited yet. If that "
					"happens, simply navigate to the folder manually once."
				],
				buttons=[
					('Okay!', self._next_step)
				]
			),
			TutorialStep(
				'',
				[
					"fman is very minimalistic by design. Should you ever miss "
					"a particular feature, you can easily fall back to %s. "
					"Please press *F10* to do this now." % native_fm
				],
				{
					'after': {
						'OpenNativeFileManager': self._after_native_fm
					}
				}
			),
			TutorialStep(
				'',
				[
					"Well done! fman opened %s in your *%s* folder."
					% (native_fm, '%s'),
					"Because fman always displays two directories, it is "
					"called a *dual-pane file manager*. Have you used one "
					"before?"
				],
				buttons=[
					('No', self._next_step), ('Yes', self._skip_steps(3))
				]
			),
			TutorialStep(
				'',
				[
					"Dual-pane file managers make it especially easy to copy "
					"and move files. Would you like to see a brief example?"
				],
				buttons=[
					('No', self._skip_steps(1)), ('Yes', self._next_step)
				]
			),
			TutorialStep(
				'',
				[
					"Okay! Press *Tab* to move from one side to the other. "
					"Then, select the file you want to copy and press *F5*. "
					"fman will ask you for confirmation. To delete the file "
					"afterwards, press *%s*. Once you are done, click the "
					"button below." % delete_key
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
					"commands as well as the shortcut for each of them.",
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
					"This completes the tutorial. Remember:",
					"* *%s* lets you go to any _P_ath." % cmd_p,
					"* *F10* opens %s" % native_fm,
					"* *%s* opens the Command _P_alette." % cmd_shift_p,
					"The Command Palette lets you find all other features.",
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
		if not dir_path:
			return
		# On Windows, QFileDialog.getExistingDirectory(...) returns paths with
		# forward slashes instead of backslashes. Because the path is used later
		# to check whether the user jumped to the right directory, we need to
		# fix this:
		dir_path = normpath(dir_path)
		self._target_directory = dir_path
		self._source_directory = self._get_source_directory(dir_path)
		self._curr_step_index += 1
		self._pane.set_path(self._source_directory, callback=self._navigate)
	def _navigate(self):
		if self._start_time is None:
			self._start_time = time()
		steps = \
			_get_navigation_steps(self._target_directory, self._pane.get_path())
		if not steps:
			# We have arrived:
			self._time_taken = time() - self._start_time
			current_dir = basename(self._pane.get_path())
			self._format_next_step_paragraph((current_dir,self._time_taken))
			self._next_step()
			return
		step = steps[0]
		step_paras = self._get_step_paras(step)
		self._steps[self._curr_step_index] = TutorialStep(
			'', step_paras, {'on': {'path_changed': self._navigate}}
		)
		if step[0] == 'open' and step[1] != '..':
			self._pane.toggle_selection(join(self._pane.get_path(), step[1]))
		self._show_current_screen()
	def _get_step_paras(self, navigation_step):
		result = []
		if not self._last_step:
			result.append(
				"fman always shows the contents of two directories. We will "
				"now navigate to your *%s* folder in the left pane." %
				basename(self._target_directory)
			)
		instruction, path = navigation_step
		encouragement = self._get_encouragement() if self._last_step else ''
		if instruction == 'show drives':
			result.append(
				"First, we need to switch to your *%s* drive. Please press "
				"*Alt+F1* to see an overview of your drives." %
				splitdrive(self._target_directory)[0]
			)
			self._last_step = 'show drives'
		elif instruction == 'open':
			result.append(
				encouragement +
				"Please%s open your *%s* folder, in one of the following "
				"ways:" % (' now' if self._last_step else '', path)
			)
			result.append(
				"* Type its name or use *Arrow Up/Down* to select it. "
				"Then, press *Enter*."
			)
			result.append("* Double-click on it with the mouse.")
		else:
			assert instruction == 'go up'
			text = encouragement + "We need to go up a%s directory. Please " \
								   "press *Backspace* to do this."
			text %= 'nother' if self._last_step == 'go up' else ''
			result.append(text)
		self._last_step = instruction
		return result
	def _get_encouragement(self):
		result = self._encouragements[self._encouragement_index]
		self._encouragement_index += 1
		self._encouragement_index %= len(self._encouragements)
		return result
	def _get_source_directory(self, target_dir):
		current = self._pane.get_path()
		if len(_get_navigation_steps(target_dir, current)) >= 3:
			return current
		home = expanduser('~')
		if is_below_dir(target_dir, home):
			if len(_get_navigation_steps(target_dir, home)) >= 3:
				return home
		return splitdrive(target_dir)[0] or '/'
	def _format_next_step_paragraph(self, *values):
		step_paras = self._steps[self._curr_step_index + 1]._paragraphs
		for i, value in enumerate(values):
			step_paras[i] %= value
	def _reset(self):
		self._pane.set_path(self._source_directory)
		self._next_step()
	def _before_goto(self):
		self._start_time = time()
		if self._target_directory == expanduser('~'):
			text = "To open your home directory with GoTo, type&nbsp;*~*. " \
				   "Then, press *Enter*."
		else:
			goto_dir = basename(self._target_directory)
			text = "Start typing *%s* into the dialog. fman will suggest " \
					"your directory. Press *Enter* to open it." % goto_dir
		self._format_next_step_paragraph((), text)
		self._next_step()
	def _after_goto(self):
		path = self._pane.get_path()
		if path == self._target_directory:
			time_taken = time() - self._start_time
			if time_taken < self._time_taken:
				paras = [
					"Awesome! Using GoTo, you jumped to your directory in "
					"*%.2f* seconds instead of *%.2f*." %
					(time_taken, self._time_taken),
					"The next time you open *%s* outside of fman, ask "
					"yourself: Isn't it tedious to click through directory "
					"trees all the time? GoTo is the answer."
					% basename(path)
				 ]
			else:
				paras = [
					"Awesome! Did you see how quick that was? Once you're used "
					"to it, you'll never want to manually navigate directory "
					"trees again."
				]
			self._steps[self._curr_step_index + 1]._paragraphs = paras
			self._next_step()
	def _after_native_fm(self):
		self._format_next_step_paragraph(basename(self._pane.get_path()))
		self._next_step()
	def _skip_steps(self, num_steps):
		return lambda: self._next_step(num_steps + 1)

def _get_navigation_steps(target_dir, source_dir):
	result = []
	target_dir = realpath(target_dir)
	target_drive = splitdrive(target_dir)[0]
	if not source_dir:
		result.append(('open', target_drive))
		source_dir = target_drive
	source_dir = realpath(source_dir)
	source_drive, source_path = splitdrive(source_dir)
	if target_drive != source_drive:
		result.append(('show drives', ''))
		result.append(('open', target_drive))
		source_dir = realpath(target_drive)
	result_samedrive = []
	rel = relpath(target_dir, source_dir)
	while rel and rel != '.':
		rel, current = split(rel)
		if current == '..':
			step = ('go up', '')
		else:
			step = ('open', current)
		result_samedrive.insert(0, step)
	result.extend(result_samedrive)
	return result