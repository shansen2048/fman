from os import makedirs
from os.path import splitext, dirname, join

import json

class JsonSupport:
	def __init__(self, json_dirs, platform_):
		self._json_dirs = json_dirs
		self._platform = platform_
		self._cache = {}
		self._save_on_quit = set()
	def load(self, name, default=None, save_on_quit=False):
		if name not in self._cache:
			result = load_json(*self._get_json_paths(name))
			if result is None:
				result = default
			self._cache[name] = result
		if save_on_quit:
			self._save_on_quit.add(name)
		return self._cache[name]
	def save(self, name, value=None):
		if value is None:
			value = self._cache[name]
		write_differential_json(value, *self._get_json_paths(name))
		self._cache[name] = value
	def on_quit(self):
		for name in self._save_on_quit:
			try:
				self.save(name)
			except ValueError as error_computing_delta:
				# This can happen for a variety of reasons. One example: When
				# multiple instances of fman are open and another instance has
				# already written to the same json file, then the delta
				# computation may fail with a ValueError. Ignore this so we can
				# at least save the other files in _save_on_quit:
				pass
	def _get_json_paths(self, name):
		base, ext = splitext(name)
		platform_specific_name = '%s (%s)%s' % (base, self._platform, ext)
		result = []
		for json_dir in self._json_dirs:
			result.append(join(json_dir, name))
			result.append(join(json_dir, platform_specific_name))
		return result

def load_json(*paths):
	result = None
	for path in paths:
		try:
			with open(path, 'r') as f:
				next_value = json.load(f)
		except FileNotFoundError:
			continue
		if result is None:
			result = type(next_value)(next_value)
			continue
		if type(next_value) != type(result):
			raise ValueError(
				'Cannot join types %s and %s.' %
				(type(next_value).__name__, type(result).__name__)
			)
		if isinstance(next_value, dict):
			result.update(next_value)
		elif isinstance(next_value, list):
			result = next_value + result
	return result

def write_differential_json(obj, *paths):
	dest_path = paths[-1]
	old_obj = load_json(*paths)
	if obj == old_obj:
		return
	if old_obj is None:
		difference = obj
	else:
		if type(obj) != type(old_obj):
			raise ValueError(
				'Cannot overwrite value of type %s with different type %s.' %
				(type(old_obj).__name__, type(obj).__name__)
			)
		if isinstance(obj, dict):
			deleted = set(key for key in old_obj if key not in obj)
			not_deletable = set(load_json(*paths[:-1]) or {})
			wrongly_deleted = deleted.intersection(not_deletable)
			if wrongly_deleted:
				raise ValueError(
					'Deleting keys %r is not supported.' % wrongly_deleted
				)
			base = load_json(*paths[:-1]) or {}
			difference = {
				key: value for key, value in obj.items()
				if key not in base or base[key] != value
			}
		elif isinstance(obj, list):
			changeable = load_json(dest_path) or []
			remainder = old_obj[len(changeable):]
			if remainder:
				if obj[-len(remainder):] != remainder:
					raise ValueError(
						"It's not possible to update list items in paths %r." %
						(paths,)
					)
				difference = obj[:-len(remainder)]
			else:
				difference = obj
		else:
			difference = obj
	makedirs(dirname(dest_path), exist_ok=True)
	with open(dest_path, 'w') as f:
		json.dump(difference, f)