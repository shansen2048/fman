from fman.impl.plugins.plugin import ExternalPlugin
from fman.impl.plugins.key_bindings import sanitize_key_bindings
from json import JSONDecodeError

SETTINGS_PLUGIN_NAME = 'Settings'

class PluginSupport:
	def __init__(self, plugins, json_io, error_handler):
		self._plugins = plugins
		self._json_io = json_io
		self._error_handler = error_handler
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
	def get_application_commands(self):
		result = set()
		for plugin in self._plugins:
			for command in plugin.get_application_commands():
				result.add(command)
		return result
	def run_application_command(self, name, args=None):
		if args is None:
			args = {}
		for plugin in self._plugins:
			if name in plugin.get_application_commands():
				return plugin.run_application_command(name, args)
		raise LookupError(name)
	def _load_plugins(self):
		result = []
		for plugin in self._plugins:
			try:
				plugin.load()
			except:
				message = 'Plugin %r failed to load.' % plugin.name
				self._error_handler.report(message)
			else:
				result.append(plugin)
		return result
	def _load_key_bindings(self):
		try:
			bindings = self.load_json('Key Bindings.json', [])
		except JSONDecodeError as e:
			self._error_handler.report(
				'Could not load key bindings: ' + e.args[0], exc=False
			)
			return []
		except:
			self._error_handler.report('Could not load key bindings.')
			return []
		else:
			available_commands = set(self._get_available_commands())
			result, errors = sanitize_key_bindings(bindings, available_commands)
			for error in errors:
				self._error_handler.report(error)
			return result
	def _get_available_commands(self):
		for plugin in self._plugins:
			yield from plugin.get_directory_pane_commands()
			yield from plugin.get_application_commands()

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