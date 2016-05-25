from fman.impl import DirectoryPaneController, DirectoryPane
from fman.impl.settings import Settings
from os.path import dirname, join, pardir, expanduser, normpath
from PyQt5.QtWidgets import QApplication, QSplitter

import sys

def get_application_context(argv):
	if getattr(sys, 'frozen', False):
		return CompiledApplicationContext(argv)
	return ApplicationContext(argv)

class ApplicationContext:
	def __init__(self, argv):
		self.argv = argv
		self._qapp = None
		self._main_window = None
		self._controller = None
		self._settings = None
	@property
	def qapp(self):
		if self._qapp is None:
			self._qapp = QApplication(self.argv)
			with open(self.get_resource('style.qss'), 'r') as style_file:
				stylesheet = style_file.read()
			self._qapp.setStyleSheet(stylesheet)
		return self._qapp
	@property
	def main_window(self):
		if self._main_window is None:
			self._main_window = QSplitter()
			self._main_window.addWidget(self.controller.left_pane)
			self._main_window.addWidget(self.controller.right_pane)
			self._main_window.setWindowTitle("fman")
			window_width = self.settings['window_width']
			window_height = self.settings['window_height']
			self._main_window.resize(window_width, window_height)
		return self._main_window
	@property
	def controller(self):
		if self._controller is None:
			self._controller = DirectoryPaneController()
			self._controller.left_pane = self._create_pane('left')
			self._controller.right_pane = self._create_pane('right')
		return self._controller
	def _create_pane(self, side):
		result = DirectoryPane(self._controller)
		settings = self.settings[side]
		location = expanduser(settings['location'])
		result.set_path(location)
		for i, width in enumerate(settings['col_widths']):
			result.file_view.setColumnWidth(i, width)
		return result
	@property
	def settings(self):
		if self._settings is None:
			default_settings = self.get_resource('default_settings.json')
			custom_settings = expanduser(join('~', '.fman', 'settings.json'))
			self._settings = Settings(default_settings, custom_settings)
		return self._settings
	def get_resource(self, *rel_path):
		res_dir = join(dirname(__file__), pardir, pardir, pardir, 'resources')
		return normpath(join(res_dir, *rel_path))

class CompiledApplicationContext(ApplicationContext):
	_libraries_inited = False
	def __init__(self, argv):
		super().__init__(argv)
		self._init_libraries()
	def _init_libraries(self):
		if not self._libraries_inited:
			import osxtrash
			so_path = self.get_resource('osxtrash.impl.cpython-34m.so')
			osxtrash.initialize(so_path=so_path)
		self.__class__._libraries_inited = True
	def get_resource(self, *rel_path):
		return normpath(join(dirname(sys.executable), *rel_path))