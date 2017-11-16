from weakref import WeakSet
from functools import lru_cache
from getpass import getuser
from os import listdir
from os.path import join, basename, expanduser, dirname, realpath, relpath, \
	pardir, splitdrive

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
	def __init__(self, source):
		self._source = iter(source)
		self._items = []
		self._items_to_skip = []
		self._items_to_add = []
		self._iterators = WeakSet()
	def remove(self, item):
		try:
			item_index = self._items.index(item)
		except ValueError:
			self._items_to_skip.append(item)
		else:
			del self._items[item_index]
			for iterator in self._iterators:
				if iterator._cur_item >= item_index:
					# Need to adjust for changed indexes now the item is gone:
					iterator._cur_item -= 1
	def add(self, item):
		# N.B.: Behaves like set#add(...), not like list#append(...)!
		self._items_to_add.append(item)
	def __iter__(iterable):
		class Iterator:
			def __init__(self):
				self._cur_item = -1
			def __next__(self):
				self._cur_item += 1
				if self._cur_item >= len(iterable._items):
					iterable._items.append(self._generate_next())
				return iterable._items[self._cur_item]
			def _generate_next(self):
				while True:
					try:
						next_item = next(iterable._source)
					except StopIteration:
						if iterable._items_to_add:
							next_item = iterable._items_to_add.pop(0)
							if next_item in iterable._items:
								continue
						else:
							raise
					items_to_skip = iterable._items_to_skip
					if items_to_skip and next_item == items_to_skip[0]:
						items_to_skip.pop(0)
					else:
						return next_item
		result = Iterator()
		iterable._iterators.add(result)
		return result