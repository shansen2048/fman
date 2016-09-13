from fman.impl.application_context import get_application_context

import sys

def main(argv):
	appctxt = get_application_context(argv)
	# Must have a QApplication before everything else:
	app = appctxt.app
	appctxt.load_fonts()
	window = appctxt.main_window
	appctxt.session_manager.on_startup(window)
	window.show_status_message('v%s ready.' % appctxt.settings['version'])
	updater = appctxt.updater
	if updater:
		updater.start()
	window.show()
	exit_code = app.exec_()
	sys.exit(exit_code)

if __name__ == '__main__':
	main(sys.argv)