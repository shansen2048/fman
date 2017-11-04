from fman.util.system import is_linux, is_windows, is_gnome_based, is_kde_based
from fman.util.qt import run_in_main_thread
from os.path import basename
from PyQt5.QtCore import QMimeData, QUrl
from PyQt5.QtWidgets import QApplication

import struct

_CFSTR_PREFERREDDROPEFFECT = 'Preferred DropEffect'
_CF_PREFERREDDROPEFFECT = \
	'application/x-qt-windows-mime;value="%s"' % _CFSTR_PREFERREDDROPEFFECT
_DROPEFFECT_MOVE = struct.pack('i', 2)

@run_in_main_thread
def clear():
	_clipboard().clear()

@run_in_main_thread
def set_text(text):
	_clipboard().setText(text)

@run_in_main_thread
def get_text():
	return _clipboard().text()

@run_in_main_thread
def copy_files(file_urls):
	if is_linux():
		extra_data = _get_extra_copy_cut_data_linux(file_urls, 'copy')
	else:
		extra_data = {}
	_place_on_clipboard(file_urls, extra_data)

@run_in_main_thread
def cut_files(file_urls):
	if is_windows():
		extra_data = {
			# Make pasting work in Explorer:
			_CFSTR_PREFERREDDROPEFFECT: _DROPEFFECT_MOVE,
			# Make pasting work in Qt:
			_CF_PREFERREDDROPEFFECT: _DROPEFFECT_MOVE
		}
	elif is_linux():
		extra_data = _get_extra_copy_cut_data_linux(file_urls, 'cut')
	else:
		raise NotImplementedError('Cutting files is not supported on this OS.')
	_place_on_clipboard(file_urls, extra_data)

@run_in_main_thread
def get_files():
	return [url.toString() for url in _clipboard().mimeData().urls()]

@run_in_main_thread
def files_were_cut():
	if is_windows():
		data = _clipboard().mimeData().data(_CF_PREFERREDDROPEFFECT)
		return data == _DROPEFFECT_MOVE
	elif is_linux():
		mime_type = _get_linux_copy_cut_mime_type()
		if mime_type:
			return _clipboard().mimeData().data(mime_type)[:4] == b'cut\n'
	return False

def _clipboard():
	return QApplication.instance().clipboard()

def _place_on_clipboard(file_urls, extra_data):
	urls = [QUrl(file_) for file_ in file_urls]
	new_clipboard_data = QMimeData()
	new_clipboard_data.setUrls(urls)
	new_clipboard_data.setText('\n'.join(map(basename, file_urls)))
	for key, value in extra_data.items():
		new_clipboard_data.setData(key, value)
	_clipboard().setMimeData(new_clipboard_data)

def _get_extra_copy_cut_data_linux(file_urls, copy_or_cut):
	result = {}
	mime_type = _get_linux_copy_cut_mime_type()
	if mime_type:
		result[mime_type] = '\n'.join([copy_or_cut] + file_urls).encode('utf-8')
	return result

def _get_linux_copy_cut_mime_type():
	if is_gnome_based():
		return 'x-special/gnome-copied-files'
	if is_kde_based():
		return 'application/x-kde-cutselection'