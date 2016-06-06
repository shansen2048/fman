from fman.util.qt import GuiThread
from fman_integrationtest import QtIT
from PyQt5.QtCore import QThread
from threading import get_ident, Condition

class GuiThreadIT(QtIT):
	def setUp(self):
		super().setUp()
		self.thread = TestThread()
		self.thread.start()
		self.thread.wait_until_running()
	def test_execute(self):
		self.assertEqual(
			self.thread.ident, self.thread.gui_thread.execute(get_ident)
		)
		self.assertNotEqual(self.thread.ident, get_ident())
	def test_execute_raises_exception(self):
		e = Exception()
		def raise_exc():
			raise e
		with self.assertRaises(Exception) as cm:
			self.thread.gui_thread.execute(raise_exc)
		self.assertIs(e, cm.exception)
	def test_execute_in_current_thread(self):
		is_running = []
		def f():
			is_running.append(True)
			return 3
		current_thread = GuiThread()
		self.assertEqual(3, current_thread.execute(f))
		self.assertTrue(is_running)
	def tearDown(self):
		self.thread.exit()
		self.thread.wait()

class TestThread(QThread):
	def __init__(self):
		super().__init__()
		self.ident = None
		self.gui_thread = None
		self._running = Condition()
	def wait_until_running(self):
		with self._running:
			self._running.wait_for(lambda: self.ident and self.gui_thread)
	def run(self):
		with self._running:
			self.ident = get_ident()
			self.gui_thread = GuiThread()
			self._running.notify()
		self.exec_()