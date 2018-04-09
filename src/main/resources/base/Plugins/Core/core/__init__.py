from core.commands import *
from core.fs import *
from datetime import datetime
from fman.fs import Column
from fman.url import basename
from math import log
from PyQt5.QtCore import QLocale, QDateTime

import fman.fs
import re

# Define here so get_default_columns(...) can reference it as core.Name:
class Name(Column):
	def __init__(self, fs=fman.fs):
		super().__init__()
		self._fs = fs
	def get_str(self, url):
		return self._fs.query(url, 'name')
	def get_sort_value(self, url, is_ascending):
		try:
			is_dir = self._fs.is_dir(url)
		except OSError:
			is_dir = False
		major = is_dir ^ is_ascending
		str_ = self.get_str(url).lower()
		minor = re.split(r'(\d+)', str_)
		is_int, is_str = 0, 1
		# re.split(...) gives a list whose first element is '' if the pattern
		# already matched at the beginning of the string. This guarantees us
		# that the integers in the string are always at odd indices in the list:
		for i in range(1, len(minor), 2):
			# Ideally, we'd just want `int(minor[i])` here. But this leads to
			# TypeErrors when the element is compared to another one that is a
			# string (`2 < "foo"`). So we return a tuple whose first element
			# indicates that this is an int:
			minor[i] = (is_int, int(minor[i]))
		for i in range(0, len(minor), 2):
			# Here, we return a tuple whose first element indicates that this is
			# not an int:
			minor[i] = (is_str, minor[i])
		# Clean up the result of re.split(...) for strings starting with digits:
		if minor[0] == (is_str, ''):
			minor = minor[1:]
		# Clean up the result of re.split(...) for strings ending with digits:
		if minor[-1] == (is_str, ''):
			minor = minor[:-1]
		return major, len(str_), minor

# Define here so get_default_columns(...) can reference it as core.Size:
class Size(Column):
	def __init__(self, fs=fman.fs):
		super().__init__()
		self._fs = fs
	def get_str(self, url):
		try:
			is_dir = self._fs.is_dir(url)
		except OSError:
			return ''
		if is_dir:
			return ''
		try:
			size_bytes = self._get_size(url)
		except OSError:
			return ''
		if size_bytes is None:
			return ''
		units = ('%d B', '%d KB', '%.1f MB', '%.1f GB')
		if size_bytes <= 0:
			unit_index = 0
		else:
			unit_index = min(int(log(size_bytes, 1024)), len(units) - 1)
		unit = units[unit_index]
		base = 1024 ** unit_index
		return unit % (size_bytes / base)
	def get_sort_value(self, url, is_ascending):
		try:
			is_dir = self._fs.is_dir(url)
		except OSError:
			is_dir = False
		if is_dir:
			ord_ = ord if is_ascending else lambda c: -ord(c)
			minor = tuple(ord_(c) for c in basename(url).lower())
		else:
			try:
				minor = self._get_size(url)
			except OSError:
				minor = 0
		return is_dir ^ is_ascending, minor
	def _get_size(self, url):
		return self._fs.query(url, 'size_bytes')

# Define here so get_default_columns(...) can reference it as core.Size:
class Modified(Column):
	def __init__(self, fs=fman.fs):
		super().__init__()
		self._fs = fs
	def get_str(self, url):
		try:
			mtime = self._get_mtime(url)
		except OSError:
			return ''
		if mtime is None:
			return ''
		mtime_qt = QDateTime.fromMSecsSinceEpoch(int(mtime.timestamp() * 1000))
		time_format = QLocale().dateTimeFormat(QLocale.ShortFormat)
		# Always show two-digit years, not four digits:
		time_format = time_format.replace('yyyy', 'yy')
		return mtime_qt.toString(time_format)
	def get_sort_value(self, url, is_ascending):
		try:
			is_dir = self._fs.is_dir(url)
		except OSError:
			is_dir = False
		try:
			mtime = self._get_mtime(url)
		except OSError:
			mtime = None
		return is_dir ^ is_ascending, mtime or datetime.min
	def _get_mtime(self, url):
		return self._fs.query(url, 'modified_datetime')