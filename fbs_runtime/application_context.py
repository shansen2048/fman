from fbs_runtime import system
from fbs_runtime.signal_ import SignalWakeupHandler
from fbs_runtime.system import is_windows, is_mac
from functools import lru_cache
from os.path import join, exists, pardir, normpath, dirname
from PyQt5.QtGui import QIcon

import sys

def cached_property(getter):
	return property(lru_cache()(getter))

class ApplicationContext:
	def __init__(self):
		# Many Qt classes require a QApplication to have been instantiated.
		# Do this here, before everything else, to achieve this:
		self.app
		# We don't build as a console app on Windows, so no point in installing
		# the SIGINT handler:
		if not is_windows():
			self._signal_wakeup_handler = SignalWakeupHandler(self.app)
			self._signal_wakeup_handler.install()
		if self.app_icon:
			self.app.setWindowIcon(self.app_icon)
	@cached_property
	def app(self):
		raise NotImplementedError()
	@cached_property
	def app_icon(self):
		if not is_mac():
			return QIcon(self.get_resource('Icon.ico'))
	def get_resource(self, *rel_path):
		raise NotImplementedError()
	def run(self):
		raise NotImplementedError()

class DevelopmentApplicationContext(ApplicationContext):
	def __init__(self, base_dir):
		self.base_dir = base_dir
		super().__init__()
	def get_resource(self, *rel_path):
		resources_dir = join(self.base_dir, 'src', 'main', 'resources')
		resource_dirs = [
			join(resources_dir, system.name().lower()),
			join(resources_dir, 'base')
		]
		for resource_dir in resource_dirs:
			resource_path = join(resource_dir, *rel_path)
			if exists(resource_path):
				return resource_path

class FrozenApplicationContext(ApplicationContext):
	def get_resource(self, *rel_path):
		if is_mac():
			rel_path = (pardir, 'Resources') + rel_path
		return normpath(join(dirname(sys.executable), *rel_path))

def is_frozen():
	return getattr(sys, 'frozen', False)