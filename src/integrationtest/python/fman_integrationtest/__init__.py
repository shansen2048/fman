from fman_unittest import TestLoader
from os.path import dirname, pardir, join
from PyQt5.QtCore import QCoreApplication, pyqtSignal, Qt
from unittest import TestCase

# See https://docs.python.org/3.5/library/unittest.html#load-tests-protocol
load_tests = TestLoader(dirname(__file__))

class QtIT(TestCase):
	def run(self, result=None):
		self.app = Application([])
		self.app.running.connect(self._run_in_app, Qt.QueuedConnection)
		self.app.running.emit(result)
		self.app.exec_()
	def _run_in_app(self, result):
		try:
			super().run(result)
		finally:
			self.app.exit()

class Application(QCoreApplication):
	running = pyqtSignal(object)

def get_resource(*rel_path):
	resources_dir = join(dirname(__file__), pardir, pardir, 'resources')
	return join(resources_dir, *rel_path)