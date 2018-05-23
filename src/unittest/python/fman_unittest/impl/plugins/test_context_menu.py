from fman.impl.plugins.context_menu import sanitize_context_menu
from unittest import TestCase

class SanitizeContextMenuTest(TestCase):
	def test_non_list(self):
		self.assertEqual(
			([], [
				'Error: Context Menu.json should be a list [...], not {...}.'
			]), sanitize_context_menu({}, [])
		)
	def test_part_non_list(self):
		self.assertEqual(
			([], [
				'Error: Context Menu.json should be a list of dicts '
				'[{...}, {...}, ...].'
			]), sanitize_context_menu([[]], [])
		)
	def test_cm_type_non_list(self):
		self.assertEqual(
			([], [
				'Error: "on_file" in Context Menu.json should be a list [...], '
				'not {...}.'
			]), sanitize_context_menu([{'on_file': {}}], [])
		)
	def test_item_non_dict(self):
		self.assertEqual(
			([], [
				'Error: Element [] of "on_file" in Context Menu.json should be '
				'a dict {...}, not [...].'
			]), sanitize_context_menu([{'on_file': [[]]}], [])
		)
	def test_no_command_no_caption(self):
		self.assertEqual(
			([], [
				'Error: Element {} of "on_file" in Context Menu.json should '
				'specify at least a "command" or a "caption".'
			]), sanitize_context_menu([{'on_file': [{}]}], [])
		)
	def test_arg_non_dict(self):
		self.assertEqual(
			([], [
				'Error in Context Menu.json: "args" must be a dict {...}, not '
				'[...].'
			]), sanitize_context_menu(
				[{'on_file': [{'command': 'foo', 'args': []}]}], ['foo']
			)
		)
	def test_separator_with_command(self):
		result = sanitize_context_menu(
			[{'on_file': [{'caption': '-', 'command': 'foo'}]}], ['foo']
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
			'Error in element %s of "on_file" in Context Menu.json: "command" '
			'cannot be used when the caption is "-".' % r
			for r in elt_reprs
		}
		self.assertIn(actual_error, possible_errors)
	def test_no_command(self):
		self.assertEqual(
			([], [
				'Error in element {"caption": "Hello"} of "on_file" in Context '
				'Menu.json: Unless the caption is "-", you must specify a '
				'"command".'
			]), sanitize_context_menu([{'on_file': [{'caption': 'Hello'}]}], [])
		)
	def test_nonexistent_command(self):
		self.assertEqual(
			([], [
				'Error in Context Menu.json: Command "foo" referenced in '
				'element {"command": "foo"} does not exist.'
			]), sanitize_context_menu([{'on_file': [{'command': 'foo'}]}], [])
		)
	def test_valid(self):
		data = [{
			'on_file': [
				{ 'command': 'cut' },
				{ 'command': 'copy_to_clipboard', 'caption': 'cut' },
				{ 'caption': '-' },
				{ 'command': 'paste' }
			],
			'in_directory': [
				{ 'command': 'create_directory', 'caption': 'New folder' },
				{ 'caption': '-' },
				{ 'command': 'properties' }
			]
		}]
		self.assertEqual(
			(data, []),
			sanitize_context_menu(
				data, [
					'cut', 'copy_to_clipboard', 'paste', 'create_directory',
					'properties'
				]
			)
		)