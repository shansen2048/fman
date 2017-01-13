from fman.impl.plugin import _get_command_name, get_command_class_name
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

class GetCommandClassNameTest(TestCase):
	def test_is_inverse_of_get_command_name(self):
		for test_string in ('C', 'Copy', 'OpenTerminal', 'MoveCursorUp'):
			result = get_command_class_name(_get_command_name(test_string))
			self.assertEqual(test_string, result)