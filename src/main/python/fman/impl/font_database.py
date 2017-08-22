from PyQt5.QtGui import QFontDatabase

class FontDatabase:
	def __init__(self):
		self._font_ids = {}
	def load(self, font_file):
		font_id = QFontDatabase.addApplicationFont(font_file)
		if font_id == -1:
			raise RuntimeError('Font %r could not be loaded.' % font_file)
		self._font_ids[font_file] = font_id
	def unload(self, font_file):
		result = \
			QFontDatabase.removeApplicationFont(self._font_ids.pop(font_file))
		if not result:
			raise RuntimeError('Could not unload font %r.' % font_file)