from fbs_runtime.system import is_mac
from fman.impl.plugins.util import describe_type

import json

class ContextMenuProvider:

	FILE_CONTEXT = 'file'
	FOLDER_CONTEXT = 'folder'

	def __init__(self, panecmd_registry, appcmd_registry, key_bindings):
		self._panecmd_registry = panecmd_registry
		self._appcmd_registry = appcmd_registry
		self._key_bindings = key_bindings
		self._sanitized_config = {}
	def load(self, config, file_name, context):
		available_commands = self._panecmd_registry.get_commands() | \
							 self._appcmd_registry.get_commands()
		sanitized, errors = \
			sanitize_context_menu(config, file_name, available_commands)
		self._sanitized_config[context] = \
			sanitized + self._sanitized_config.get(context, [])
		return errors
	# The extra `file_name` parameter is there so unload(...) has the same
	# signature as load(...). This is required so ContextMenuProvider can be
	# used with ExternalPlugin#_configure_component_from_json(...).
	def unload(self, config, file_name, context):
		try:
			for elt in config:
				try:
					self._sanitized_config[context].remove(elt)
				except ValueError as not_in_list:
					pass
		except TypeError as not_iterable:
			pass
	def get_context_menu(self, pane, file_under_mouse=None):
		context = self.FOLDER_CONTEXT if file_under_mouse is None \
			else self.FILE_CONTEXT
		for entry in self._sanitized_config.get(context, []):
			caption = entry.get('caption')
			if caption == '-':
				yield ('-', '', '')
				continue
			cmd_name = entry['command']
			if cmd_name in pane.get_commands():
				if not self._panecmd_registry.is_command_visible(
					cmd_name, pane, file_under_mouse
				):
					continue
				def run_command(cmd_name, args):
					self._panecmd_registry.execute_command(
						cmd_name, args, pane, file_under_mouse
					)
				caption = caption or pane.get_command_aliases(cmd_name)[0]
			else:
				run_command = self._appcmd_registry.execute_command
				caption = caption or \
						  self._appcmd_registry\
							  .get_command_aliases(cmd_name)[0]
			args = entry.get('args', {})
			# Need `r=run_command,...` to create one lambda per loop:
			callback = lambda r=run_command, c=cmd_name, a=args: r(c, a)
			all_shortcuts = self._get_shortcuts_for_command(cmd_name)
			try:
				shortcut = next(iter(all_shortcuts))
			except StopIteration:
				shortcut = ''
			yield (caption, shortcut, callback)
	def _get_shortcuts_for_command(self, command):
		for binding in self._key_bindings.get_sanitized_bindings():
			if binding['command'] != command:
				continue
			shortcut = binding['keys'][0]
			if is_mac():
				shortcut = _insert_mac_key_symbols(shortcut)
			yield shortcut

def sanitize_context_menu(cm, file_name, available_commands):
	if not isinstance(cm, list):
		return [], [(
			'Error: %s should be a list [...], not %s.'
			% (file_name, describe_type(cm))
		)]
	result, errors = [], []
	for item in cm:
		if not isinstance(item, dict):
			errors.append(
				'Error in %s: Element %s should be a dict {...}, not %s.' %
				(file_name, json.dumps(item), describe_type(item))
			)
			continue
		caption = item.get('caption')
		command = item.get('command')
		if command:
			if caption == '-':
				errors.append(
					'Error in %s, element %s: "command" cannot be used when '
					'the caption is "-".' % (file_name, json.dumps(item))
				)
				continue
			if command not in available_commands:
				errors.append(
					'Error in %s: Command %s referenced in element %s does not '
					'exist.' %
					(file_name, json.dumps(command), json.dumps(item))
				)
				continue
			args = item.get('args')
			if args is not None and not isinstance(args, dict):
				errors.append(
					'Error in %s: "args" must be a dict {...}, not %s.'
					% (file_name, describe_type(args))
				)
				continue
		else:
			if not caption:
				errors.append(
					'Error in %s: Element %s should specify at least a '
					'"command" or a "caption".' % (file_name, json.dumps(item))
				)
				continue
			if caption != '-':
				errors.append(
					'Error in %s, element %s: Unless the caption is "-", you '
					'must specify a "command".' % (file_name, json.dumps(item))
				)
				continue
		result.append(item)
	return result, errors

# Copied from the Core plugin:
def _insert_mac_key_symbols(shortcut):
	keys = shortcut.split('+')
	return ''.join(_KEY_SYMBOLS_MAC.get(key, key) for key in keys)

# Copied from the Core plugin:
_KEY_SYMBOLS_MAC = {
	'Cmd': '⌘', 'Alt': '⌥', 'Ctrl': '⌃', 'Shift': '⇧', 'Backspace': '⌫',
	'Up': '↑', 'Down': '↓', 'Left': '←', 'Right': '→', 'Enter': '↩'
}