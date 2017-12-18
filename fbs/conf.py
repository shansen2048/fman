from os.path import normpath, join

OPTIONS = {}

def path(relpath):
	try:
		project_dir = OPTIONS['project_dir']
	except KeyError:
		error_message = \
			"Please set OPTIONS['project_dir'] before calling this function"
		raise RuntimeError(error_message) from None
	return normpath(join(project_dir, *relpath.split('/')))