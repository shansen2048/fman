from fman.impl.html_style import highlight, underline
from fman.impl.widgets import Overlay
from fman.util.qt import run_in_main_thread, connect_once

import re

class TutorialController:
	def __init__(self, tutorial_class, args):
		self._tutorial_class = tutorial_class
		self._args = args
		self._tutorial = None
	def start(self):
		if self._tutorial:
			self._tutorial.close()
		self._tutorial = self._tutorial_class(*self._args)
		self._tutorial.start()

class Tutorial:
	def __init__(self, main_window, app, command_callback, metrics):
		self._main_window = main_window
		self._app = app
		self._command_callback = command_callback
		self._metrics = metrics
		self._curr_step_index = -1
		self._curr_step = None
		self._steps = self._get_steps()
	def _get_steps(self):
		raise NotImplementedError()
	@property
	def _pane(self):
		return self._main_window.get_panes()[0]
	def start(self):
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
		self._pane.path_changed.disconnect(self._curr_step.on_path_changed)
		self._curr_step = None
	def _next_step(self, delta=1):
		self._curr_step_index += delta
		self._track_current_step()
		self._show_current_screen()
	def _track_current_step(self):
		self._metrics.track(
			'StartedTutorialStep', {'step': self._curr_step_index}
		)
	def _show_current_screen(self):
		if self._curr_step:
			self.close()
		self._curr_step = self._steps[self._curr_step_index]
		self._command_callback.add_listener(self._curr_step)
		self._pane.path_changed.connect(self._curr_step.on_path_changed)
		self._curr_step.show(self._main_window)
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
		self._quicksearch = quicksearch
		quicksearch.shown.connect(self._on_quicksearch_shown)
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
	def on_path_changed(self, _):
		try:
			action = self._command_actions['on']['path_changed']
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
		result = ''
		is_list = False
		for line in self._paragraphs:
			if line.startswith('* '):
				line = '<li style="line-height: 150%%;">%s</li>' % \
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