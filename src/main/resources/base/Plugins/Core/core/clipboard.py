from core.os_ import is_gnome_based, is_kde_based
from fman import PLATFORM
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

def copy_files(files):
	if PLATFORM == 'Linux':
		extra_data = _get_extra_copy_cut_data_linux(files, 'copy')
	else:
		extra_data = {}
	_place_on_clipboard(files, extra_data)

def cut_files(files):
	if PLATFORM == 'Windows':
		extra_data = {
			# Make pasting work in Explorer:
			_CFSTR_PREFERREDDROPEFFECT: _DROPEFFECT_MOVE,
			# Make pasting work in Qt:
			_CF_PREFERREDDROPEFFECT: _DROPEFFECT_MOVE
		}
	elif PLATFORM == 'Linux':
		extra_data = _get_extra_copy_cut_data_linux(files, 'cut')
	else:
		raise NotImplementedError(PLATFORM)
	_place_on_clipboard(files, extra_data)

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
	if PLATFORM == 'Windows':
		data = _clipboard().mimeData().data(_CF_PREFERREDDROPEFFECT)
		return data == _DROPEFFECT_MOVE
	elif PLATFORM == 'Linux':
		mime_type = _get_linux_copy_cut_mime_type()
		if mime_type:
			return _clipboard().mimeData().data(mime_type)[:4] == b'cut\n'
	return False

def _clipboard():
	return QApplication.instance().clipboard()

def _place_on_clipboard(files, extra_data):
	urls = [QUrl.fromLocalFile(file_) for file_ in files]
	new_clipboard_data = QMimeData()
	new_clipboard_data.setUrls(urls)
	new_clipboard_data.setText('\n'.join(map(basename, files)))
	for key, value in extra_data.items():
		new_clipboard_data.setData(key, value)
	_clipboard().setMimeData(new_clipboard_data)

def _get_extra_copy_cut_data_linux(files, copy_or_cut):
	result = {}
	mime_type = _get_linux_copy_cut_mime_type()
	if mime_type:
		file_urls = [QUrl.fromLocalFile(f).toString() for f in files]
		result[mime_type] = '\n'.join([copy_or_cut] + file_urls).encode('utf-8')
	return result

def _get_linux_copy_cut_mime_type():
	if is_gnome_based():
		return 'x-special/gnome-copied-files'
	if is_kde_based():
		return 'application/x-kde-cutselection'