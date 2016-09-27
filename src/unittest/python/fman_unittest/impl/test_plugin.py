from fman.impl.plugin import Plugin
from unittest import TestCase

class PluginTest(TestCase):
	def test_single_letter(self):
		self.assertEqual('c', self._get_command_name('C'))
	def test_single_word(self):
		self.assertEqual('copy', self._get_command_name('Copy'))
	def test_two_words(self):
		self.assertEqual(
			'open_terminal', self._get_command_name('OpenTerminal')
		)
	def test_three_words(self):
		self.assertEqual(
			'move_cursor_up', self._get_command_name('MoveCursorUp')
		)
	def test_two_consecutive_upper_case_chars(self):
		self.assertEqual('get_url', self._get_command_name('GetURL'))
	def _get_command_name(self, command_class_name):
		return Plugin('dummy')._get_command_name(command_class_name)