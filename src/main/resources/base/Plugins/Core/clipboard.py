from fman import platform
from os.path import basename, normpath
from PyQt5.QtCore import QMimeData, QUrl
from PyQt5.QtWidgets import QApplication

import struct

_CFSTR_PREFERREDDROPEFFECT = 'Preferred DropEffect'
_CF_PREFERREDDROPEFFECT = \
	'application/x-qt-windows-mime;value="%s"' % _CFSTR_PREFERREDDROPEFFECT
_DROPEFFECT_MOVE = struct.pack('i', 2)

def clear():
	_clipboard().clear()

def set_text(text):
	_clipboard().setText(text)

def copy_files(files, extra_data=None):
	if extra_data is None:
		extra_data = {}
	urls = [QUrl.fromLocalFile(file_) for file_ in files]
	new_clipboard_data = QMimeData()
	new_clipboard_data.setUrls(urls)
	new_clipboard_data.setText('\n'.join(map(basename, files)))
	for key, value in extra_data.items():
		new_clipboard_data.setData(key, value)
	_clipboard().setMimeData(new_clipboard_data)

def cut_files(files):
	if platform() == 'Windows':
		copy_files(files, {
			# Make pasting work in Explorer:
			_CFSTR_PREFERREDDROPEFFECT: _DROPEFFECT_MOVE,
			# Make pasting work in Qt:
			_CF_PREFERREDDROPEFFECT: _DROPEFFECT_MOVE
		})
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
	if platform() == 'Windows':
		data = _clipboard().mimeData().data(_CF_PREFERREDDROPEFFECT)
		return data == _DROPEFFECT_MOVE
	return False

def _clipboard():
	return QApplication.instance().clipboard()