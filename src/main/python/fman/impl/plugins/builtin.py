from fman import ApplicationCommand
from fman.impl.plugins.plugin import Plugin

class BuiltinPlugin(Plugin):
	def __init__(self, tutorial_controller, *super_args):
		super().__init__(*super_args)
		self._register_application_command(Tutorial, tutorial_controller)
	@property
	def name(self):
		return 'Builtin'

class Tutorial(ApplicationCommand):
	def __init__(self, tutorial_controller):
		super().__init__()
		self._tutorial_controller = tutorial_controller
	def __call__(self):
		self._tutorial_controller.start()