from os.path import normpath, join

OPTIONS = {}

def path(relpath):
	try:
		project_dir = OPTIONS['project_dir']
	except KeyError:
		raise RuntimeError("Please set OPTIONS['project_dir']") from None
	return normpath(join(project_dir, *relpath.split('/')))