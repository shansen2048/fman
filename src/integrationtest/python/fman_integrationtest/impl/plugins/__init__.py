from os.path import exists

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
	def __init__(self):
		self.loaded_css_files = []
	def load(self, css_file_path):
		if exists(css_file_path):
			self.loaded_css_files.append(css_file_path)
		else:
			raise FileNotFoundError(css_file_path)
	def unload(self, css_file_path):
		self.loaded_css_files.remove(css_file_path)

class StubFontDatabase:
	def __init__(self):
		self.loaded_fonts = []
	def load(self, font_file):
		self.loaded_fonts.append(font_file)
	def unload(self, font_file):
		self.loaded_fonts.remove(font_file)