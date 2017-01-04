from fman.impl.plugin import _get_command_name
from unittest import TestCase

class GetCommandNameTest(TestCase):
	def test_single_letter(self):
		self.assertEqual('c', _get_command_name('C'))
	def test_single_word(self):
		self.assertEqual('copy', _get_command_name('Copy'))
	def test_two_words(self):
		self.assertEqual(
			'open_terminal', _get_command_name('OpenTerminal')
		)
	def test_three_words(self):
		self.assertEqual(
			'move_cursor_up', _get_command_name('MoveCursorUp')
		)
	def test_two_consecutive_upper_case_chars(self):
		self.assertEqual('get_url', _get_command_name('GetURL'))