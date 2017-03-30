from fman import ApplicationCommand, DirectoryPaneCommand, DirectoryPaneListener

class TestCommand(ApplicationCommand):
	RAN = False
	def __call__(self, ran):
		self.__class__.RAN = ran

class CommandRaisingError(DirectoryPaneCommand):
	def __call__(self):
		raise ValueError()

class ListenerRaisingError(DirectoryPaneListener):
	def on_path_changed(self):
		raise ValueError()
	def on_doubleclicked(self, file_path):
		raise ValueError()
	def on_name_edited(self, file_path, new_name):
		raise ValueError()