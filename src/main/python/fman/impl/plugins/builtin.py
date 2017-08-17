from fman import ApplicationCommand
from fman.impl.plugins.plugin import Plugin

class BuiltinPlugin(Plugin):
	def __init__(self, error_handler, command_callback, key_bindings, tutorial):
		super().__init__(error_handler, command_callback, key_bindings)
		self._register_application_command(Tutorial, tutorial)
	@property
	def name(self):
		return 'Builtin'

class Tutorial(ApplicationCommand):
	def __init__(self, tutorial):
		self._tutorial = tutorial
	def __call__(self):
		self._tutorial.start()