from fman.impl.application_context import get_application_context

import sys

def main(argv):
	appctxt = get_application_context(argv)
	# Must have a QApplication before everything else:
	app = appctxt.app
	window = appctxt.main_window
	settings_manager = appctxt.settings_manager
	settings_manager.on_startup(window)
	window.status_bar.showMessage('Ready.')
	window.show()
	exit_code = app.exec_()
	sys.exit(exit_code)

if __name__ == '__main__':
	main(sys.argv)