from fman.impl.plugins.plugin import ExternalPlugin
from fman.impl.plugins.key_bindings import sanitize_key_bindings

SETTINGS_PLUGIN_NAME = 'Settings'

class PluginSupport:
	def __init__(
		self, plugin_factory, key_bindings, config, builtin_plugin=None
	):
		self._plugin_factory = plugin_factory
		self._key_bindings = key_bindings
		self._config = config
		self._builtin_plugin = builtin_plugin
		self._external_plugins = {}
		self._panes = []
	def load_plugin(self, plugin_dir):
		plugin = self._plugin_factory(plugin_dir)
		success = plugin.load()
		if success:
			self._external_plugins[plugin_dir] = plugin
			# Give the plugin a chance to register DirectoryPaneCommands and
			# ...Listeners for existing panes:
			for pane in self._panes:
				plugin.on_pane_added(pane)
		return success
	def unload_plugin(self, plugin_path):
		try:
			plugin = self._external_plugins.pop(plugin_path)
		except KeyError:
			message = 'Plugin %r is not loaded.' % plugin_path
			raise ValueError(message) from None
		plugin.unload()
	def load_json(self, name, default=None, save_on_quit=False):
		return self._config.load_json(name, default, save_on_quit)
	def save_json(self, name, value=None):
		self._config.save_json(name, value)
	def get_sanitized_key_bindings(self):
		return self._key_bindings.get_sanitized_bindings()
	def register_pane(self, pane):
		for plugin in self._plugins:
			plugin.on_pane_added(pane)
		self._panes.append(pane)
	def get_panes(self):
		return self._panes
	def get_application_commands(self):
		result = set()
		for plugin in self._plugins:
			for command in plugin.get_application_commands():
				result.add(command)
		return result
	def get_application_command_aliases(self, command_name):
		for plugin in self._plugins:
			try:
				command = plugin.get_application_commands()[command_name]
			except KeyError:
				continue
			else:
				return command.aliases
		raise LookupError(command_name)
	def run_application_command(self, name, args=None):
		if args is None:
			args = {}
		for plugin in self._plugins:
			if name in plugin.get_application_commands():
				return plugin.run_application_command(name, args)
		raise LookupError(name)
	def get_active_pane(self):
		for pane in self._panes:
			if pane._has_focus():
				return pane
	def get_context_menu(self, pane, file_under_mouse=None):
		for entry in self.load_json('Context Menu.json', default=[]):
			cmd_name = entry['command']
			if cmd_name in pane.get_commands():
				with pane._override_file_under_cursor(file_under_mouse):
					if not pane.is_command_visible(cmd_name):
						continue
				def run_command(cmd_name):
					pane.run_command(
						cmd_name, file_under_cursor=file_under_mouse
					)
				def_caption = pane.get_command_aliases(cmd_name)[0]
			else:
				run_command = self.run_application_command
				def_caption = self.get_application_command_aliases(cmd_name)[0]
			caption = entry.get('caption', def_caption)
			# Need `c=cmd_name` to create one lambda per loop:
			callback = lambda c=cmd_name: run_command(c)
			yield (caption, callback)
	@property
	def _plugins(self):
		if self._builtin_plugin is not None:
			yield self._builtin_plugin
		yield from self._external_plugins.values()

class PluginFactory:
	def __init__(
		self, config, theme, font_database, error_handler, command_callback,
		key_bindings, mother_fs, window
	):
		self._config = config
		self._theme = theme
		self._font_database = font_database
		self._error_handler = error_handler
		self._command_callback = command_callback
		self._key_bindings = key_bindings
		self._mother_fs = mother_fs
		self._window = window
	def __call__(self, plugin_dir):
		return ExternalPlugin(
			plugin_dir, self._config, self._theme, self._font_database,
			self._error_handler, self._command_callback, self._key_bindings,
			self._mother_fs, self._window
		)

class CommandCallback:
	def __init__(self, metrics):
		self._metrics = metrics
		self._listeners = []
	def add_listener(self, listener):
		self._listeners.append(listener)
	def remove_listener(self, listener):
		self._listeners.remove(listener)
	def before_command(self, name):
		self._metrics.track('RanCommand', {
			'command': name
		})
		for listener in self._listeners[:]:
			listener.before_command(name)
	def after_command(self, name):
		for listener in self._listeners[:]:
			listener.after_command(name)