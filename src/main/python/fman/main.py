from fman.impl.application_context import ApplicationContext

import sys

def main(argv):
	appctxt = ApplicationContext(argv)
	app = appctxt.qapp
	window = appctxt.main_window
	controller = appctxt.controller
	appctxt.settings.apply(window, controller.left_pane, controller.right_pane)
	window.show()
	exit_code = app.exec_()
	appctxt.settings.save(window, controller.left_pane, controller.right_pane)
	sys.exit(exit_code)

if __name__ == '__main__':
	main(sys.argv)