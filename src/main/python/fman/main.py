from fman.impl.application_context import get_application_context

import sys

def main(argv):
	appctxt = get_application_context(argv)
	# Must have a QApplication before everything else:
	app = appctxt.app
	window = appctxt.main_window
	controller = appctxt.controller
	appctxt.settings.apply(window, controller.left_pane, controller.right_pane)
	window.show()
	appctxt.status_bar.showMessage('Ready.')
	exit_code = app.exec_()
	appctxt.settings.save(window, controller.left_pane, controller.right_pane)
	sys.exit(exit_code)

if __name__ == '__main__':
	main(sys.argv)