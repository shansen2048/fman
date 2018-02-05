class StubErrorHandler:
	def __init__(self):
		self.error_messages = []
		self.exceptions = []
	def report(self, message, exc=None):
		self.error_messages.append(message)
		self.exceptions.append(exc)