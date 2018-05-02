from fman.impl.application_context import get_application_context

import cProfile
import sys

def main():
	appctxt = get_application_context()
	exit_code = appctxt.run()
	sys.exit(exit_code)

if __name__ == '__main__':
	if len(sys.argv) > 1 and sys.argv[1] == '--profile':
		sys.argv.pop(1)
		cProfile.run('main()', filename='fman.profile', sort='cumtime')
	else:
		main()