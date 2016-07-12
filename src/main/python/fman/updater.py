from threading import Thread

class EskyUpdater(Thread):
	def __init__(self, executable, update_url):
		super().__init__()
		from esky import Esky
		self.esky = Esky(executable, update_url)
	def run(self):
		self.esky.auto_update()

class OSXUpdater(Thread):
	def run(self):
		pass