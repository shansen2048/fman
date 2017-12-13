from threading import Lock
from functools import lru_cache
from getpass import getuser
from os import listdir, strerror
from os.path import join, basename, expanduser, dirname, realpath, relpath, \
	pardir, splitdrive

import errno
import os
import sys

def listdir_absolute(dir_path):
	return [join(dir_path, file_name) for file_name in listdir(dir_path)]

def get_user():
	try:
		return getuser()
	except:
		return basename(expanduser('~'))

def is_below_dir(file_path, directory):
	if splitdrive(file_path)[0].lower() != splitdrive(directory)[0].lower():
		return False
	rel = relpath(realpath(dirname(file_path)), realpath(directory))
	return not (rel == pardir or rel.startswith(pardir + os.sep))

def parse_version(version_str):
	if version_str.endswith('-SNAPSHOT'):
		version_str = version_str[:-len('-SNAPSHOT')]
	return tuple(map(int, version_str.split('.')))

def cached_property(getter):
	return property(lru_cache()(getter))

def is_frozen():
	return getattr(sys, 'frozen', False)

def is_debug():
	return not is_frozen()

class MixinBase:

	_FIELDS = () # To be set by subclasses

	def _get_field_values(self):
		return tuple(getattr(self, field) for field in self._FIELDS)

class EqMixin(MixinBase):
	def __eq__(self, other):
		try:
			return self._get_field_values() == other._get_field_values()
		except AttributeError:
			return False
	def __ne__(self, other):
		return not self.__eq__(other)
	def __hash__(self):
		return hash(self._get_field_values())

class ReprMixin(MixinBase):
	def __repr__(self):
		return '%s(%s)' % (
			self.__class__.__name__,
			', '.join(
				'%s=%r' % (field, val)
				for (field, val) in zip(self._FIELDS, self._get_field_values())
			)
		)

class ConstructorMixin(MixinBase):
	def __init__(self, *args):
		super().__init__()
		for field, arg in zip(self._FIELDS, args):
			setattr(self, field, arg)

class Event:
	def __init__(self):
		self._callbacks = []
	def add_callback(self, callback):
		self._callbacks.append(callback)
	def remove_callback(self, callback):
		self._callbacks.remove(callback)
	def trigger(self, *args):
		for callback in self._callbacks:
			callback(*args)

class CachedIterable:

	_DELETED = object()

	def __init__(self, source):
		"""
		This constructor must(!) raise `TypeError` if source is not an iterable.
		"""
		self._source = iter(source)
		self._lock = Lock()
		self._items = []
		self._items_to_skip = []
		self._items_to_add = []
	def remove(self, item):
		try:
			item_index = self._items.index(item)
		except ValueError:
			self._items_to_skip.append(item)
		else:
			self._items[item_index] = self._DELETED
	def add(self, item):
		# N.B.: Behaves like set#add(...), not like list#append(...)!
		self._items_to_add.append(item)
	def __iter__(self):
		return _CachedIterator(self)
	def get_next(self, pointer):
		with self._lock:
			for pointer in range(pointer, len(self._items)):
				item = self._items[pointer]
				if item is not self._DELETED:
					return pointer + 1, item
			return pointer + 1, self._generate_next()
	def _generate_next(self):
		while True:
			try:
				result = next(self._source)
			except StopIteration:
				for i, result in enumerate(self._items_to_add):
					if result not in self._items:
						self._items_to_add = self._items_to_add[i + 1:]
						break
				else:
					raise
			if self._items_to_skip and result == self._items_to_skip[0]:
				self._items_to_skip.pop(0)
			else:
				self._items.append(result)
				return result

class _CachedIterator:
	def __init__(self, parent):
		self._parent = parent
		self._pointer = 0
	def __next__(self):
		self._pointer, result = self._parent.get_next(self._pointer)
		return result

# Copied from core.util:
def filenotfounderror(path):
	# The correct way of instantiating FileNotFoundError in a way that respects
	# the parent class (OSError)'s arguments:
	return FileNotFoundError(errno.ENOENT, strerror(errno.ENOENT), path)