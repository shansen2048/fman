from fman.impl.plugins.context_menu import sanitize_context_menu
from unittest import TestCase

class SanitizeContextMenuTest(TestCase):
	def test_non_list(self):
		self.assertEqual(
			([], [
				'Error: Context Menu.json should be a list [...], not {...}.'
			]), self._sanitize_context_menu({})
		)
	def test_entry_non_dict(self):
		self.assertEqual(
			([], [
				'Error in Context Menu.json: Element [] should be a dict '
				'{...}, not [...].'
			]), self._sanitize_context_menu([[]])
		)
	def test_no_command_no_caption(self):
		self.assertEqual(
			([], [
				'Error in Context Menu.json: Element {} should specify at '
				'least a "command" or a "caption".'
			]), self._sanitize_context_menu([{}])
		)
	def test_arg_non_dict(self):
		self.assertEqual(
			([], [
				'Error in Context Menu.json: "args" must be a dict {...}, not '
				'[...].'
			]), self._sanitize_context_menu(
				[{'command': 'foo', 'args': []}], ['foo']
			)
		)
	def test_separator_with_command(self):
		result = self._sanitize_context_menu(
			[{'caption': '-', 'command': 'foo'}], ['foo']
		)
		self.assertEqual([], result[0])
		self.assertIsInstance(result[1], list)
		self.assertEqual(1, len(result[1]))
		actual_error, = result[1]
		elt_reprs = {
			'{"caption": "-", "command": "foo"}',
			'{"command": "foo", "caption": "-"}'
		}
		possible_errors = {
			'Error in Context Menu.json, element %s: "command" '
			'cannot be used when the caption is "-".' % r
			for r in elt_reprs
		}
		self.assertIn(actual_error, possible_errors)
	def test_no_command(self):
		self.assertEqual(
			([], [
				'Error in Context Menu.json, element {"caption": "Hello"}: '
				'Unless the caption is "-", you must specify a "command".'
			]), self._sanitize_context_menu([{'caption': 'Hello'}])
		)
	def test_nonexistent_command(self):
		self.assertEqual(
			([], [
				'Error in Context Menu.json: Command "foo" referenced in '
				'element {"command": "foo"} does not exist.'
			]), self._sanitize_context_menu([{'command': 'foo'}])
		)
	def test_valid(self):
		data = [
			{ 'command': 'cut' },
			{ 'command': 'copy_to_clipboard', 'caption': 'cut' },
			{ 'caption': '-' },
			{ 'command': 'paste' }
		]
		self.assertEqual(
			(data, []),
			self._sanitize_context_menu(
				data, ['cut', 'copy_to_clipboard', 'paste']
			)
		)
	def _sanitize_context_menu(self, cm, available_commands=None):
		if available_commands is None:
			available_commands = []
		return sanitize_context_menu(
			cm, 'Context Menu.json', available_commands
		)