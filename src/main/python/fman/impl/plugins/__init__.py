from fman.impl.plugins.plugin import ExternalPlugin
from fman.impl.plugins.key_bindings import sanitize_key_bindings

SETTINGS_PLUGIN_NAME = 'Settings'

class PluginSupport:
	def __init__(
		self, builtin_plugins, error_handler, command_callback, key_bindings,
		config, theme, font_database
	):
		self._plugins = builtin_plugins
		self._error_handler = error_handler
		self._command_callback = command_callback
		self._key_bindings = key_bindings
		self._config = config
		self._theme = theme
		self._font_database = font_database
	def load_plugin(self, plugin_dir):
		plugin = ExternalPlugin(
			self._error_handler, self._command_callback, self._key_bindings,
			plugin_dir, self._config, self._theme, self._font_database
		)
		if plugin.load():
			self._plugins.append(plugin)
	def load_json(self, name, default=None, save_on_quit=False):
		return self._config.load_json(name, default, save_on_quit)
	def save_json(self, name, value=None):
		self._config.save_json(name, value)
	def get_sanitized_key_bindings(self):
		return self._key_bindings.get_sanitized_bindings()
	def on_pane_added(self, pane):
		for plugin in self._plugins:
			plugin.on_pane_added(pane)
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
				return command.get_aliases()
		raise LookupError(command_name)
	def run_application_command(self, name, args=None):
		if args is None:
			args = {}
		for plugin in self._plugins:
			if name in plugin.get_application_commands():
				return plugin.run_application_command(name, args)
		raise LookupError(name)

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