from os.path import normpath, join

class LazyOptions:
	def __init__(self):
		self.cache = {}
	def __getitem__(self, item):
		return self.cache[item]
	def __setitem__(self, key, value):
		self.cache[key] = value
	def update(self, other):
		for key, value in other.items():
			self[key] = value
	def items(self):
		return self.cache.items()

def path(relpath):
	try:
		project_dir = OPTIONS['project_dir']
	except KeyError:
		error_message = \
			"Please set OPTIONS['project_dir'] before calling this function"
		raise RuntimeError(error_message) from None
	return normpath(join(project_dir, *relpath.split('/')))

OPTIONS = LazyOptions()