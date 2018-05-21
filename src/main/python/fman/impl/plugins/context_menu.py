class ContextMenuProvider:
	def __init__(self, config, panecmd_registry, appcmd_registry):
		self._config = config
		self._panecmd_registry = panecmd_registry
		self._appcmd_registry = appcmd_registry
	def get_context_menu(self, pane, file_under_mouse=None):
		settings = self._config.load_json('Context Menu.json', default=[])
		key = 'directory' if file_under_mouse is None else 'files'
		for entry in settings[key]:
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
				def_caption = pane.get_command_aliases(cmd_name)[0]
			else:
				run_command = self._appcmd_registry.execute_command
				def_caption = \
					self._appcmd_registry.get_command_aliases(cmd_name)[0]
			caption = entry.get('caption', def_caption)
			# Need `c=cmd_name` to create one lambda per loop:
			callback = lambda c=cmd_name: run_command(c)
			from core.commands import _get_shortcuts_for_command
			try:
				shortcut = next(iter(_get_shortcuts_for_command(cmd_name)))
			except StopIteration:
				shortcut = ''
			yield (caption, shortcut, callback)