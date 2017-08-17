from PyQt5.QtGui import QFontDatabase

class FontDatabase:
	def load(self, font_file):
		QFontDatabase.addApplicationFont(font_file)