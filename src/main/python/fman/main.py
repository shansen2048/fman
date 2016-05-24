from fman.impl.application_context import ApplicationContext

import sys

if __name__ == '__main__':
	appl_ctxt = ApplicationContext(sys.argv)
	app = appl_ctxt.qapp
	appl_ctxt.main_window.show()
	sys.exit(app.exec_())