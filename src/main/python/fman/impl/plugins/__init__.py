from fman.impl.plugins.plugin import Plugin
from fman.impl.plugins.key_bindings import sanitize_key_bindings
from os.path import basename

USER_PLUGIN_NAME = 'User'

class PluginSupport:
	def __init__(self, plugin_dirs, json_io, error_handler):
		self._plugin_dirs = plugin_dirs
		self._json_io = json_io
		self._error_handler = error_handler
		self._plugins = None
		self._key_bindings = None
	def initialize(self):
		self._plugins = self._load_plugins()
		self._key_bindings = self._load_key_bindings()
	def load_json(self, name, default=None, save_on_quit=False):
		return self._json_io.load(name, default, save_on_quit)
	def save_json(self, name, value=None):
		self._json_io.save(name, value)
	def get_sanitized_key_bindings(self):
		return self._key_bindings
	def on_pane_added(self, pane):
		for plugin in self._plugins:
			plugin.on_pane_added(pane)
	def _load_plugins(self):
		result = []
		for plugin_dir in self._plugin_dirs:
			try:
				plugin = Plugin.load(plugin_dir, self._error_handler)
			except:
				message = 'Plugin %r failed to load.' % basename(plugin_dir)
				self._error_handler.report(message)
			else:
				result.append(plugin)
		return result
	def _load_key_bindings(self):
		try:
			bindings = self.load_json('Key Bindings.json', [])
		except:
			self._error_handler.report('Error: Could not load key bindings.')
			return []
		else:
			available_commands = set(self._get_available_commands())
			result, errors = sanitize_key_bindings(bindings, available_commands)
			for error in errors:
				self._error_handler.report(error)
			return result
	def _get_available_commands(self):
		for plugin in self._plugins:
			for command_name in plugin.get_command_names():
				yield command_name