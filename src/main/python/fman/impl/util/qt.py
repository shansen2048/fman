from fman.url import splitscheme, as_human_readable, as_url
from functools import wraps
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QThread, QEvent, QUrl
from PyQt5.QtWidgets import QApplication

def connect_once(signal, slot):
	def _connect_once(*args, **kwargs):
		signal.disconnect(_connect_once)
		slot(*args, **kwargs)
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

def _main_thread():
	return QApplication.instance().thread()

run_in_main_thread = run_in_thread(_main_thread)

def is_in_main_thread():
	return QThread.currentThread() == _main_thread()

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

def disable_window_animations_mac(window):
	# We need to access `.winId()` below. This method has an unwanted (and not
	# very well-documented) side effect: Calling it before the window is shown
	# makes Qt turn the window into a "native window". This incurs performance
	# penalties and leads to subtle changes in behaviour. We therefore wait for
	# the Show event:
	def eventFilter(target, event):
		from objc import objc_object
		view = objc_object(c_void_p=int(target.winId()))
		NSWindowAnimationBehaviorNone = 2
		view.window().setAnimationBehavior_(NSWindowAnimationBehaviorNone)
	FilterEventOnce(window, QEvent.Show, eventFilter)

class FilterEventOnce(QObject):
	def __init__(self, parent, event_type, callback):
		super().__init__(parent)
		self._event_type = event_type
		self._callback = callback
		parent.installEventFilter(self)
	def eventFilter(self, target, event):
		if event.type() == self._event_type:
			self.parent().removeEventFilter(self)
			self._callback(target, event)
		return False

def as_qurl(url):
	scheme, path = splitscheme(url)
	if scheme == 'file://':
		# Qt's file:// URLs are slightly different from ours. In
		# particular, on Windows, we use file://C:/foo where Qt uses
		# file:///C:/foo (three slashes).
		return QUrl.fromLocalFile(as_human_readable(url))
	return QUrl(url)

def from_qurl(qurl):
	return as_url(qurl.toLocalFile())

AscendingOrder = Qt.AscendingOrder
WA_MacShowFocusRect = Qt.WA_MacShowFocusRect
TextAlignmentRole = Qt.TextAlignmentRole
AlignRight = Qt.AlignRight
AlignTop = Qt.AlignTop
AlignVCenter = Qt.AlignVCenter
FramelessWindowHint = Qt.FramelessWindowHint
ClickFocus = Qt.ClickFocus
NoFocus = Qt.NoFocus
KeyboardModifier = Qt.KeyboardModifier
NoModifier = Qt.NoModifier
ControlModifier = Qt.ControlModifier
ShiftModifier = Qt.ShiftModifier
AltModifier = Qt.AltModifier
MetaModifier = Qt.MetaModifier
KeypadModifier = Qt.KeypadModifier
GroupSwitchModifier = Qt.GroupSwitchModifier
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
Key_Escape = Qt.Key_Escape
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
Key_Tab = Qt.Key_Tab
Key_Shift = Qt.Key_Shift
Key_Control = Qt.Key_Control
Key_Meta = Qt.Key_Meta
Key_Alt = Qt.Key_Alt
Key_AltGr = Qt.Key_AltGr
Key_CapsLock = Qt.Key_CapsLock
Key_NumLock = Qt.Key_NumLock
Key_ScrollLock = Qt.Key_ScrollLock
ItemIsEnabled = Qt.ItemIsEnabled
ItemIsEditable = Qt.ItemIsEditable
ItemIsSelectable = Qt.ItemIsSelectable
EditRole = Qt.EditRole
DisplayRole = Qt.DisplayRole
ToolTipRole = Qt.ToolTipRole
UserRole = Qt.UserRole
SizeHintRole = Qt.SizeHintRole
DecorationRole = Qt.DecorationRole
ItemIsDragEnabled = Qt.ItemIsDragEnabled
ItemIsDropEnabled = Qt.ItemIsDropEnabled
CopyAction = Qt.CopyAction
MoveAction = Qt.MoveAction
IgnoreAction = Qt.IgnoreAction
NoButton = Qt.NoButton