class StubErrorHandler:
	def __init__(self):
		self.error_messages = []
	def report(self, message, exc=None):
		self.error_messages.append(message)

class StubCommandCallback:
	def before_command(self, command_name):
		pass
	def after_command(self, command_name):
		pass

class StubTheme:
	def load(self, css_file_path):
		pass

class StubFontDatabase:
	def load(self, font_file):
		pass