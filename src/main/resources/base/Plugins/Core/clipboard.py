from fman import platform
from os.path import basename, normpath
from PyQt5.QtCore import QMimeData
from PyQt5.QtCore import QUrl
from PyQt5.QtWidgets import QApplication

import struct

_DROPEFFECT_MOVE = 2
_GMEM_MOVEABLE = 0x0002

def clear():
	_clipboard().clear()

def set_text(text):
	_clipboard().setText(text)

def copy_files(files):
	urls = [QUrl.fromLocalFile(file_) for file_ in files]
	new_clipboard_data = QMimeData()
	new_clipboard_data.setUrls(urls)
	new_clipboard_data.setText('\n'.join(map(basename, files)))
	_clipboard().setMimeData(new_clipboard_data)

def cut_files(files):
	if platform() == 'windows':
		from ctypes import windll, sizeof
		from ctypes.wintypes import DWORD
		from win32clipboard import OpenClipboard, RegisterClipboardFormat, \
			SetClipboardData, CloseClipboard
		from win32com.shell import shellcon

		copy_files(files)

		kernel32 = windll.kernel32
		hData = kernel32.GlobalAlloc(_GMEM_MOVEABLE, sizeof(DWORD))
		pData = kernel32.GlobalLock(hData)
		DWORD.from_address(pData).value = _DROPEFFECT_MOVE
		kernel32.GlobalUnlock(hData)
		OpenClipboard(None)
		CF_PREFERREDDROPEFECT = \
			RegisterClipboardFormat(shellcon.CFSTR_PREFERREDDROPEFFECT)
		SetClipboardData(CF_PREFERREDDROPEFECT, hData)
		CloseClipboard()
	else:
		raise NotImplementedError(platform())

def get_files():
	result = []
	for url in _clipboard().mimeData().urls():
		if url.isLocalFile():
			# On (at least) OS X, url.toLocalFile() returns paths of the form
			# '/foo/bar/' for directories. But os.path.basename('/foo/bar/')
			# returns '' instead of 'bar', which has lead to bugs in the past.
			# We use normpath(...) here to get rid of the trailing slash:
			result.append(normpath(url.toLocalFile()))
	return result

def files_were_cut():
	if platform() == 'windows':
		from win32com.shell import shellcon
		key = 'application/x-qt-windows-mime;value="%s"' % \
			  shellcon.CFSTR_PREFERREDDROPEFFECT
		data = _clipboard().mimeData().data(key)
		return data == struct.pack('i', _DROPEFFECT_MOVE)
	return False

def _clipboard():
	return QApplication.instance().clipboard()