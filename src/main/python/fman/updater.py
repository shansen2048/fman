from esky import Esky
from threading import Thread

class Updater(Thread):
	def __init__(self, executable, update_url):
		super().__init__()
		self.esky = Esky(executable, update_url)
	def run(self):
		self.esky.auto_update()