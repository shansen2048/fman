from fbs_runtime.system import is_mac
from fman.impl.plugins.util import describe_type

import json

class ContextMenuProvider:
	def __init__(self, config, panecmd_registry, appcmd_registry, key_bindings):
		self._config = config
		self._panecmd_registry = panecmd_registry
		self._appcmd_registry = appcmd_registry
		self._key_bindings = key_bindings
		self._sanitized_config = {}
	def load(self, config):
		available_commands = self._panecmd_registry.get_commands() | \
							 self._appcmd_registry.get_commands()
		sanitized, errors = sanitize_context_menu(config, available_commands)
		self._sanitized_config.update(sanitized)
		return errors
	def unload(self, config):
		try:
			keys = config.keys()
		except AttributeError:
			return
		for key in keys:
			self._sanitized_config.pop(key)
	def get_context_menu(self, pane, file_under_mouse=None):
		key = 'directory' if file_under_mouse is None else 'files'
		for entry in self._sanitized_config.get(key, []):
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
				def run_command(c=cmd_name):
					self._panecmd_registry.execute_command(
						c, {}, pane, file_under_mouse
					)
				caption = caption or pane.get_command_aliases(cmd_name)[0]
			else:
				run_command = self._appcmd_registry.execute_command
				caption = caption or \
						  self._appcmd_registry.get_command_aliases(cmd_name)[0]
			# Need `c=cmd_name` to create one lambda per loop:
			callback = lambda c=cmd_name: run_command(c)
			try:
				shortcut = next(iter(self._get_shortcuts_for_command(cmd_name)))
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

def sanitize_context_menu(cm, available_commands):
	if not isinstance(cm, dict):
		return {}, [(
			'Error: Context Menu.json should be a dict {...}, not %s.'
			% describe_type(cm)
		)]
	result, errors = {}, []
	for cm_type, items in cm.items():
		if not isinstance(items, list):
			errors.append(
				'Error: "%s" in Context Menu.json should be a list [...], not '
				'%s.' % (cm_type, describe_type(items))
			)
			continue
		sanitized_items = []
		for item in items:
			if not isinstance(item, dict):
				errors.append(
					'Error: Element %s of "%s" in Context Menu.json should be '
					'a dict {...}, not %s.' %
					(json.dumps(item), cm_type, describe_type(item))
				)
				continue
			caption = item.get('caption')
			command = item.get('command')
			if command:
				if caption == '-':
					errors.append(
						'Error in element %s of "%s" in Context Menu.json: '
						'"command" cannot be used when the caption is "-".'
						% (json.dumps(item), cm_type)
					)
					continue
				if command not in available_commands:
					errors.append(
						'Error in Context Menu.json: Command %s referenced in '
						'element %s does not exist.' %
						(json.dumps(command), json.dumps(item))
					)
					continue
			else:
				if not caption:
					errors.append(
						'Error: Element %s of "%s" in Context Menu.json should '
						'specify at least a "command" or a "caption".' %
						(json.dumps(item), cm_type)
					)
					continue
				if caption != '-':
					errors.append(
						'Error in element %s of "%s" in Context Menu.json: '
						'Unless the caption is "-", you must specify a '
						'"command".' % (json.dumps(item), cm_type)
					)
					continue
			sanitized_items.append(item)
		if sanitized_items:
			result[cm_type] = sanitized_items
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