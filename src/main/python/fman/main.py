from fman.impl.application_context import get_application_context

import sys

def main():
	appctxt = get_application_context()
	appctxt.setup_signals()
	exit_code = appctxt.run()
	sys.exit(exit_code)

if __name__ == '__main__':
	main()