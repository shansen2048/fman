from os import makedirs, getpid, unlink, replace
from os.path import dirname, splitext, join

import json

class Config:
	def __init__(self, platform):
		self._platform = platform
		self._plugin_dirs = []
		self._cache = {}
		self._save_on_quit = set()
	def add_dir(self, dir_path):
		self._plugin_dirs.append(dir_path)
		self._reload_cache()
	def remove_dir(self, dir_path):
		self._plugin_dirs.remove(dir_path)
		self._reload_cache()
	def load_json(self, json_name, default=None, save_on_quit=False):
		if json_name in self._cache:
			result = self._cache[json_name]
		else:
			result = load_json(self.locate(json_name))
			if result is None:
				result = default
			if result is not None:
				self._cache[json_name] = result
		if save_on_quit and result is not None:
			self._save_on_quit.add(json_name)
		return result
	def save_json(self, json_name, value=None):
		if value is None:
			value = self._cache[json_name]
		locations = self.locate(json_name)
		dest = locations[-1]
		# Some users complained about corrupted Visited Paths.json files.
		# Looking at the files, it appears that they were concurrently
		# overwritten. To avoid this, write to a temp file first, then use
		# atomic operation replace(...) to move to the destination:
		tmp_file = dest + '.tmp%d' % getpid()
		try:
			write_differential_json(value, locations[:-1] + [tmp_file])
			replace(tmp_file, dest)
		finally:
			try:
				unlink(tmp_file)
			except FileNotFoundError:
				pass
		self._cache[json_name] = value
	def locate(self, file_name, in_dir=None):
		base, ext = splitext(file_name)
		platform_specific_name = '%s (%s)%s' % (base, self._platform, ext)
		result = []
		dirs_to_search = [in_dir] if in_dir else self._plugin_dirs
		for dir_ in dirs_to_search:
			result.append(join(dir_, file_name))
			result.append(join(dir_, platform_specific_name))
		return result
	def on_quit(self):
		for json_name in self._save_on_quit:
			try:
				self.save_json(json_name)
			except ValueError as error_computing_delta:
				# This can happen for a variety of reasons. One example: When
				# multiple instances of fman are open and another instance has
				# already written to the same json file, then the delta
				# computation may fail with a ValueError. Ignore this so we can
				# at least save the other files in _save_on_quit:
				pass
	def _reload_cache(self):
		old_cache = self._cache
		self._cache = {}
		for json_name, old in old_cache.items():
			new = self.load_json(json_name)
			if isinstance(old, dict) and isinstance(new, dict):
				old.clear()
				old.update(new)
				new = old
			elif isinstance(old, list) and isinstance(new, list):
				old.clear()
				old.extend(new)
				new = old
			if new is not None:
				self._cache[json_name] = new
			elif json_name in self._save_on_quit:
				self._cache[json_name] = old

def load_json(paths):
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

def write_differential_json(obj, paths):
	dest_path = paths[-1]
	old_obj = load_json(paths)
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
			not_deletable = set(load_json(paths[:-1]) or {})
			wrongly_deleted = deleted.intersection(not_deletable)
			if wrongly_deleted:
				raise ValueError(
					'Deleting keys %r is not supported.' % wrongly_deleted
				)
			base = load_json(paths[:-1]) or {}
			difference = {
				key: value for key, value in obj.items()
				if key not in base or base[key] != value
			}
		elif isinstance(obj, list):
			changeable = load_json([dest_path]) or []
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