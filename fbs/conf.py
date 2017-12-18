from os.path import normpath, join, dirname, isabs

import json

OPTIONS = {}

def load_options(json_path):
	result = {}
	with open(json_path, 'r') as f:
		result_raw = json.load(f)
	default_settings = join(dirname(__file__), 'build.json.default')
	extends = result_raw.pop('extends', [default_settings])
	for extended in extends:
		if not isabs(extended):
			extended = join(dirname(json_path), extended)
		result.update(load_options(extended))
	result.update(result_raw)
	return result

def path(relpath):
	try:
		project_dir = OPTIONS['project_dir']
	except KeyError:
		raise RuntimeError("Please set OPTIONS['project_dir']") from None
	return normpath(join(project_dir, *relpath.split('/')))