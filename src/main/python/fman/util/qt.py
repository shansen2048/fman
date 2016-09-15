from functools import wraps
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QThread
from PyQt5.QtWidgets import QApplication

def connect_once(signal, slot):
	def _connect_once(*args, **kwargs):
		slot(*args, **kwargs)
		signal.disconnect(_connect_once)
	signal.connect(_connect_once)

def run_in_thread(thread_fn):
	def decorator(f):
		@wraps(f)
		def result(*args, **kwargs):
			thread = thread_fn()
			if QThread.currentThread() == thread:
				return f(*args, **kwargs)
			task = Task(f, args, kwargs)
			receiver = Receiver(task)
			receiver.moveToThread(thread)
			sender = Sender()
			sender.signal.connect(receiver.slot, Qt.BlockingQueuedConnection)
			sender.signal.emit()
			return task.result
		return result
	return decorator

run_in_main_thread = run_in_thread(lambda: QApplication.instance().thread())

class Task:
	def __init__(self, fn, args, kwargs):
		self.fn = fn
		self.args = args
		self.kwargs = kwargs
		self.has_run = False
		self._result = self._exception = None
	def __call__(self):
		try:
			self._result = self.fn(*self.args, **self.kwargs)
		except Exception as e:
			self._exception = e
		finally:
			self.has_run = True
	@property
	def result(self):
		if not self.has_run:
			raise ValueError("Hasn't run.")
		if self._exception:
			raise self._exception
		return self._result

class Sender(QObject):
	signal = pyqtSignal()

class Receiver(QObject):
	def __init__(self, callback, parent=None):
		super().__init__(parent)
		self.callback = callback
	def slot(self):
		self.callback()

AscendingOrder = Qt.AscendingOrder
WA_MacShowFocusRect = Qt.WA_MacShowFocusRect
TextAlignmentRole = Qt.TextAlignmentRole
AlignVCenter = Qt.AlignVCenter
ClickFocus = Qt.ClickFocus
KeyboardModifier = Qt.KeyboardModifier
NoModifier = Qt.NoModifier
ControlModifier = Qt.ControlModifier
ShiftModifier = Qt.ShiftModifier
AltModifier = Qt.AltModifier
MetaModifier = Qt.MetaModifier
KeypadModifier = Qt.KeypadModifier
Key_Down = Qt.Key_Down
Key_Up = Qt.Key_Up
Key_Left = Qt.Key_Left
Key_Right = Qt.Key_Right
Key_Home = Qt.Key_Home
Key_End = Qt.Key_End
Key_PageUp = Qt.Key_PageUp
Key_PageDown = Qt.Key_PageDown
Key_Space = Qt.Key_Space
Key_Insert = Qt.Key_Insert
Key_Help = Qt.Key_Help
Key_Backspace = Qt.Key_Backspace
Key_Enter = Qt.Key_Enter
Key_Return = Qt.Key_Return
Key_F2 = Qt.Key_F2
Key_F4 = Qt.Key_F4
Key_F5 = Qt.Key_F5
Key_F6 = Qt.Key_F6
Key_F7 = Qt.Key_F7
Key_F8 = Qt.Key_F8
Key_F9 = Qt.Key_F9
Key_F10 = Qt.Key_F10
Key_F11 = Qt.Key_F11
Key_Delete = Qt.Key_Delete
ItemIsEnabled = Qt.ItemIsEnabled
ItemIsEditable = Qt.ItemIsEditable
ItemIsSelectable = Qt.ItemIsSelectable
EditRole = Qt.EditRole