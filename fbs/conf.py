from os.path import normpath, join, dirname

import json

class LazyOptions:
	def __init__(self):
		self.cache = {}
	def __getitem__(self, item):
		return self.cache[item]
	def __setitem__(self, key, value):
		self.cache[key] = value
		if key == 'release':
			self.update(read_filter())
	def update(self, other):
		for key, value in other.items():
			self[key] = value
	def items(self):
		return self.cache.items()

def read_filter():
	with open(path('src/main/filters/filter-local.json'), 'r') as f:
		result = json.load(f)
	if OPTIONS['release']:
		with open(path('src/main/filters/filter-release.json'), 'r') as f:
			result.update(json.load(f))
	return result

def path(relpath):
	return normpath(join(OPTIONS['project_dir'], *relpath.split('/')))

OPTIONS = LazyOptions()
OPTIONS['project_dir'] = dirname(dirname(__file__))
OPTIONS.update({
	'release': False,
	'files_to_filter': []
})