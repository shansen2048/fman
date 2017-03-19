from fman.impl.application_context import get_application_context

import sys

def main():
	appctxt = get_application_context()
	appctxt.initialize()
	appctxt.main_window.show()
	exit_code = appctxt.app.exec_()
	sys.exit(exit_code)

if __name__ == '__main__':
	main()