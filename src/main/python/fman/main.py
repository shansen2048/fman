from fman.impl.application_context import get_application_context

import sys

def main():
	appctxt = get_application_context()
	appctxt.initialize()
	window = appctxt.main_window
	window.show_status_message('v%s ready.' % appctxt.constants['version'])
	window.show()
	exit_code = appctxt.app.exec_()
	sys.exit(exit_code)

if __name__ == '__main__':
	main()