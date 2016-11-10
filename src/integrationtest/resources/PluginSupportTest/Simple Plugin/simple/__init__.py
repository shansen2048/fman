from fman import DirectoryPaneCommand, DirectoryPaneListener

class TestCommand(DirectoryPaneCommand):
	def __call__(self, success):
		return success

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