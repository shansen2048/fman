from ctypes import sizeof
from os.path import splitdrive, exists, basename
from PyQt5.QtCore import QUrl, QMimeData
from subprocess import Popen

import struct
import sys

class OS:
	def __init__(self, clipboard):
		self.clipboard = clipboard
	def move_to_trash(self, *files):
		raise NotImplementedError()
	def get_applications_directory(self):
		raise NotImplementedError()
	def get_applications_filter(self):
		raise NotImplementedError()
	def open_file_with_app(self, file_, app):
		Popen([app, file_])
	def open_terminal_in_directory(self, dir_):
		raise NotImplementedError()
	def open_native_file_manager(self, dir_):
		raise NotImplementedError()
	def copy_files_to_clipboard(self, files):
		urls = [QUrl.fromLocalFile(file_) for file_ in files]
		new_clipboard_data = QMimeData()
		new_clipboard_data.setUrls(urls)
		new_clipboard_data.setText('\n'.join(map(basename, files)))
		self.clipboard.setMimeData(new_clipboard_data)
	def cut_files_to_clipboard(self, files):
		raise NotImplementedError()
	def get_files_in_clipboard(self):
		clipboard_urls = self.clipboard.mimeData().urls()
		return [
			url.toLocalFile() for url in clipboard_urls if url.isLocalFile()
		]
	def files_in_clipboard_were_cut(self):
		return False

class OSX(OS):
	def move_to_trash(self, *files):
		from osxtrash import move_to_trash
		return move_to_trash(*files)
	def get_applications_directory(self):
		return '/Applications'
	def get_applications_filter(self):
		return "Applications (*.app)"
	def open_file_with_app(self, file_, app):
		Popen(['/usr/bin/open', '-a', app, file_])
	def open_terminal_in_directory(self, dir_):
		self.open_file_with_app(dir_, 'Terminal')
	def open_native_file_manager(self, dir_):
		self.open_file_with_app(dir_, 'Finder')

class Windows(OS):
	def move_to_trash(self, *files):
		from send2trash import send2trash
		for file in files:
			send2trash(file)
	def get_applications_directory(self):
		result = r'c:\Program Files'
		if not exists(result):
			result = splitdrive(sys.executable)[0] + '\\'
		return result
	def get_applications_filter(self):
		return "Applications (*.exe)"
	def open_terminal_in_directory(self, dir_):
		Popen('start cmd', shell=True, cwd=dir_)
	def open_native_file_manager(self, dir_):
		Popen(['start', 'explorer', dir_], shell=True)
	def cut_files_to_clipboard(self, files):
		from ctypes import windll
		from ctypes.wintypes import DWORD
		from win32clipboard import OpenClipboard, RegisterClipboardFormat, \
			SetClipboardData, CloseClipboard
		from win32com.shell import shellcon

		self.copy_files_to_clipboard(files)

		kernel32 = windll.kernel32
		hData = kernel32.GlobalAlloc(GMEM_MOVEABLE, sizeof(DWORD))
		pData = kernel32.GlobalLock(hData)
		DWORD.from_address(pData).value = DROPEFFECT_MOVE
		kernel32.GlobalUnlock(hData)
		OpenClipboard(None)
		CF_PREFERREDDROPEFECT = \
			RegisterClipboardFormat(shellcon.CFSTR_PREFERREDDROPEFFECT)
		SetClipboardData(CF_PREFERREDDROPEFECT, hData)
		CloseClipboard()
	def files_in_clipboard_were_cut(self):
		key = 'application/x-qt-windows-mime;value="%s"' % \
			  CFSTR_PREFERREDDROPEFFECT
		data = self.clipboard.mimeData().data(key)
		return data == struct.pack('i', DROPEFFECT_MOVE)

GMEM_MOVEABLE = 0x0002
DROPEFFECT_MOVE = 2
CFSTR_PREFERREDDROPEFFECT = 'Preferred DropEffect'

class Linux(OS):
	def move_to_trash(self, *files):
		from send2trash import send2trash
		for file in files:
			send2trash(file)
	def get_applications_directory(self):
		return r'/usr/bin'
	def get_applications_filter(self):
		return "Applications (*)"
	def open_terminal_in_directory(self, dir_):
		Popen('gnome-terminal', shell=True, cwd=dir_)
	def open_native_file_manager(self, dir_):
		Popen(['gnome-open', dir_], shell=True)