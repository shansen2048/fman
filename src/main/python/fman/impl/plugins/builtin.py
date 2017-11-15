from fman import ApplicationCommand
from fman.impl.plugins.plugin import Plugin

class BuiltinPlugin(Plugin):
	def __init__(self, tutorial, *super_args):
		super().__init__(*super_args)
		self._register_application_command(Tutorial, tutorial)
	@property
	def name(self):
		return 'Builtin'

class Tutorial(ApplicationCommand):
	def __init__(self, tutorial):
		super().__init__()
		self._tutorial = tutorial
	def __call__(self):
		self._tutorial.start()