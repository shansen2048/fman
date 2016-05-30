from os.path import dirname, join, pardir, basename, normpath

class TestLoader:
	def __init__(self, dir_):
		self.dir = dir_
	def __call__(self, loader, standard_tests, pattern):
		if pattern is None:
			pattern = 'test*.py'
		package_tests = loader.discover(
			start_dir=self.dir, pattern=pattern, top_level_dir=_PROJECT_HOME
		)
		standard_tests.addTests(package_tests)
		return standard_tests

_PROJECT_HOME = dirname(__file__)
while basename(_PROJECT_HOME) != 'src':
	_PROJECT_HOME = normpath(join(_PROJECT_HOME, pardir))
_PROJECT_HOME = normpath(join(_PROJECT_HOME, pardir))

# See https://docs.python.org/3.5/library/unittest.html#load-tests-protocol
load_tests = TestLoader(dirname(__file__))