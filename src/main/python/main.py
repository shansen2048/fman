from impl import get_main_window
from PyQt5.QtWidgets import QApplication

import sys

if __name__ == '__main__':
	app = QApplication(sys.argv)
	style = open('../resources/style.qss').read()
	QApplication.instance().setStyleSheet(style)
	root_path = '/Users/michael/dev/django'
	window = get_main_window(root_path, root_path)
	window.show()
	sys.exit(app.exec_())