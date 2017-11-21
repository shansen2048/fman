from fman import ApplicationCommand
from fman.fs import FileSystem, Column
from fman.impl.plugins.plugin import Plugin

class BuiltinPlugin(Plugin):
	def __init__(self, tutorial_controller, *super_args):
		super().__init__(*super_args)
		self._register_application_command(Tutorial, tutorial_controller)
		self._register_file_system(NullFileSystem)
		self._register_column(NullColumn)
	@property
	def name(self):
		return 'Builtin'

class Tutorial(ApplicationCommand):
	def __init__(self, window, tutorial_controller):
		super().__init__(window)
		self._tutorial_controller = tutorial_controller
	def __call__(self):
		self._tutorial_controller.start()

class NullFileSystem(FileSystem):

	scheme = 'null://'

	def get_default_columns(self, path):
		return 'NullColumn',
	def iterdir(self, path):
		return []
	def is_dir(self, path):
		return not path
	def exists(self, path):
		return not path

class NullColumn(Column):

	name = 'null'

	def get_str(self, url):
		return ''
	def get_sort_value(self, url, is_ascending):
		return None