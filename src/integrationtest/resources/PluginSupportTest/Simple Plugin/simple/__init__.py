from fman import DirectoryPaneCommand

class TestCommand(DirectoryPaneCommand):
	def __call__(self, success):
		return success