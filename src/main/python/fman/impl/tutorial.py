from fman.impl.widgets import Overlay
from fman.util import listdir_absolute
from fman.util.qt import run_in_main_thread, connect_once
from fman.util.system import is_mac
from os import listdir
from os.path import expanduser, isdir, join, getmtime, basename, samefile, \
	abspath

import os
import re

class Tutorial:
	def __init__(self, main_window, app, command_callback, metrics):
		self._main_window = main_window
		self._app = app
		self._command_callback = command_callback
		self._metrics = metrics
		self._curr_step_index = -1
		self._curr_step = None
		self._starting_directory = None
		self._directory_for_goto = self._get_directory_for_goto()
		self._steps = self._get_steps()
	def start(self):
		self._starting_directory = self._get_pane_path()
		self._curr_step_index = -1
		self._next_step()
	def reject(self):
		self._metrics.track('AbortedTutorial', {'step': self._curr_step_index})
		self.close()
	def complete(self):
		self._metrics.track('CompletedTutorial')
		self.close()
	def close(self):
		self._curr_step.close()
		self._command_callback.remove_listener(self._curr_step)
		self._curr_step = None
	def _next_step(self):
		self._curr_step_index += 1
		self._metrics.track(
			'StartedTutorialStep', {'step': self._curr_step_index}
		)
		self._show_current_screen()
	def _show_current_screen(self):
		if self._curr_step:
			self.close()
		self._curr_step = self._steps[self._curr_step_index]
		self._command_callback.add_listener(self._curr_step)
		self._curr_step.show(self._main_window)
	def _get_directory_for_goto(self):
		home_dir = expanduser('~')
		candidates = (
			join(home_dir, 'Dropbox'), join(home_dir, 'Downloads'),
			os.environ.get('PROGRAMW6432', r'C:\Program Files'),
			os.environ.get('PROGRAMFILES', r'C:\Program Files (x86)')
		)
		for candidate in candidates:
			if isdir(candidate):
				return candidate
		other_candidate_in_home = self._get_best_directory_for_goto(home_dir)
		if other_candidate_in_home:
			return other_candidate_in_home
		root_drive = abspath(os.sep)
		return self._get_best_directory_for_goto(root_drive)
	def _get_best_directory_for_goto(self, root_path):
		result = []
		for d in listdir_absolute(root_path):
			if basename(d).startswith('.') or not isdir(d):
				continue
			try:
				sort_key = not listdir(d), len(basename(d)), getmtime(d)
			except OSError:
				pass
			else:
				result.append((sort_key, d))
		if result:
			return sorted(result)[0][1]
	def _get_steps(self):
		goto_directory = basename(self._directory_for_goto)
		cmd_p = '⌘P' if is_mac() else 'Ctrl+P'
		cmd_shift_p = 'Cmd+Shift+P' if is_mac() else 'Ctrl+Shift+P'
		return [
			TutorialStep(
				'Welcome to fman!',
				[
					"Would you like to take a quick tour of the most useful "
					"features? It only takes ~2 minutes and lets you hit the "
					"ground running."
				],
				buttons=[('No', self.reject), ('Yes', self._next_step)]
			),
			TutorialStep(
				'Awesome!',
				[
					"First things first: You'll be most productive when you "
					"use fman with the keyboard. Try to resort to the mouse as "
					"little as possible.",
					"Ready? Let's try fman's most useful shortcut:<br/>Press "
					"*%s*." % cmd_p
				],
				{
					'before': {
						'GoTo': self._after_quicksearch_shown(self._next_step)
					}
				}
			),
			TutorialStep(
				'',
				[
					"This is fman's *GoTo* dialog. It lets you quickly jump to "
					"directories.",
					"Type *%s* into the dialog. Then, press *Enter*. "
					"This should open your %s folder." %
					(goto_directory[:4], goto_directory)
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
					"Well done! Did you notice how quick that was? Once you're "
					"used to it, you'll never want to manually navigate "
					"directory trees again.",
					"Feel free to jump to a few other directories (the "
					"shortcut was %s). When you're ready to continue, "
					"click *Next*." % cmd_p
				],
				buttons=[('Next', self._next_step)]
			),
			TutorialStep(
				'',
				[
					"Next, let's try the \"mother of all shortcuts\". Press "
					"*%s*." % cmd_shift_p
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
					"This is the *Command Palette*. It's basically a "
					"searchable list of fman's features. Note how it displays "
					"the shortcut for each command!",
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
					"This concludes the tutorial. Remember:",
					"* *%s* lets you go to any _P_ath." % cmd_p,
					"* *%s* opens the Command _P_alette." % cmd_shift_p,
					"* fman is best used with the keyboard.",
					"Because the Command Palette lets you look up other "
					"features, that's all you need to know.",
					"Have fun with fman! :-)"
				],
				buttons=[('Close', self.complete)]
			)
		]
	def _after_goto(self):
		path = self._get_pane_path()
		if path != self._starting_directory:
			self._next_step()
	def _get_pane_path(self):
		return self._main_window.get_panes()[0].get_path()
	def _after_quicksearch_shown(self, callback):
		return AfterQuicksearchShown(self._main_window, callback)

class AfterQuicksearchShown:
	def __init__(self, main_window, callback):
		self._main_window = main_window
		self._callback = callback
		self._quicksearch = None
	@run_in_main_thread
	def __call__(self):
		connect_once(
			self._main_window.before_quicksearch, self._before_quicksearch
		)
	def _before_quicksearch(self, quicksearch):
		quicksearch.shown.connect(self._on_quicksearch_shown)
		self._quicksearch = quicksearch
	def _on_quicksearch_shown(self):
		self._quicksearch.shown.disconnect(self._on_quicksearch_shown)
		self._callback()

class TutorialStep:
	def __init__(self, title, paragraphs, command_actions=None, buttons=None):
		self._title = title
		self._paragraphs = paragraphs
		self._buttons = buttons or []
		self._command_actions = command_actions or {}
		self._screen = None
	@run_in_main_thread
	def show(self, parent):
		self._screen = Overlay(parent, self._get_html(), self._buttons)
		parent.show_overlay(self._screen)
	@run_in_main_thread
	def close(self):
		self._screen.close()
		self._screen = None
	def before_command(self, name):
		try:
			action = self._command_actions['before'][name]
		except KeyError:
			pass
		else:
			action()
	def after_command(self, name):
		try:
			action = self._command_actions['after'][name]
		except KeyError:
			pass
		else:
			action()
	def _get_html(self):
		return self._get_title_html() + self._get_body_html()
	def _get_title_html(self):
		if not self._title:
			return ''
		return "<center style='line-height: 130%'>" \
					"<h2 style='color: #bbbbbb;'>" + self._title + "</h2>" \
				"</center>"
	def _get_body_html(self):
		highlight = lambda text: "<span style='color: white;'>%s</span>" % text
		def underline(text):
			return "<span style='text-decoration: underline;'>%s</span>" % text
		result = ''
		is_list = False
		for line in self._paragraphs:
			if line.startswith('* '):
				line = '<li style="line-height: 150%%;">&nbsp;%s</li>' % \
					   line[2:]
				if not is_list:
					line = '<ul>' + line
					is_list = True
			else:
				line = '<p style="line-height: 115%%;">%s</p>' % line
				if is_list:
					line = '</ul>' + line
					is_list = False
			line = re.subn(r'\*([^*]+)\*', highlight(r'\1'), line)[0]
			line = re.subn(r'_([^_]+)_', underline(r'\1'), line)[0]
			result += line
		return result