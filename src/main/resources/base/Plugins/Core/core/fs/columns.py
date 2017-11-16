from datetime import datetime
from fman.fs import Column
from fman.url import splitscheme
from math import log
from os.path import basename, getsize, getmtime

import fman.fs
import re

class NameColumn(Column):

	name = 'Name'

	def __init__(self, fs=fman.fs):
		super().__init__()
		self._fs = fs
	def get_str(self, url):
		if re.match('/+', url):
			return '/'
		url = url.rstrip('/')
		try:
			return url[url.rindex('/')+1:]
		except ValueError:
			return url
	def get_sort_value(self, url, is_ascending):
		is_dir = self._fs.is_dir(url)
		return is_dir ^ is_ascending, basename(url).lower()

class SizeColumn(Column):

	name = 'Size'

	def __init__(self, fs=fman.fs):
		super().__init__()
		self._fs = fs
	def get_str(self, url):
		if self._fs.is_dir(url):
			return ''
		try:
			size_bytes = self._get_size(url)
		except OSError:
			return ''
		units = ('%d bytes', '%d KB', '%.1f MB', '%.1f GB')
		if size_bytes <= 0:
			unit_index = 0
		else:
			unit_index = min(int(log(size_bytes, 1024)), len(units) - 1)
		unit = units[unit_index]
		base = 1024 ** unit_index
		return unit % (size_bytes / base)
	def get_sort_value(self, url, is_ascending):
		is_dir = self._fs.is_dir(url)
		if is_dir:
			ord_ = ord if is_ascending else lambda c: -ord(c)
			minor = tuple(ord_(c) for c in basename(url).lower())
		else:
			minor = self._get_size(url)
		return is_dir ^ is_ascending, minor
	def _get_size(self, url):
		scheme, path = splitscheme(url)
		if scheme != 'file://':
			raise ValueError('Unsupported scheme: %r' % scheme)
		return getsize(path)

class LastModifiedColumn(Column):

	name = 'Modified'

	def __init__(self, fs=fman.fs):
		super().__init__()
		self._fs = fs
	def get_str(self, url):
		try:
			mtime = self._get_mtime(url)
		except OSError:
			return ''
		return datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
	def get_sort_value(self, url, is_ascending):
		is_dir = self._fs.is_dir(url)
		return is_dir ^ is_ascending, self._get_mtime(url)
	def _get_mtime(self, url):
		scheme, path = splitscheme(url)
		if scheme != 'file://':
			raise ValueError('Unsupported scheme: %r' % scheme)
		return getmtime(path)