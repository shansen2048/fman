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

def is_in_subdir(file_path, directory):
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

class Signal:
	def __init__(self):
		self._callbacks = []
	def connect(self, callback):
		self._callbacks.append(callback)
	def disconnect(self, callback):
		self._callbacks.remove(callback)
	def emit(self, *args):
		for callback in self._callbacks:
			callback(*args)

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