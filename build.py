from build_impl import path, run, is_windows, is_osx, is_linux
from os import unlink, listdir, remove, pathsep
from os.path import join, isdir, isfile, islink
from shutil import rmtree

OPTIONS = {
	'version': '0.0.1',
	'local_staticfiles_dir': '/Users/michael/dev/fman.io/static',
	'server_staticfiles_dir': '/home/fman/src/static',
	'server_user': 'fman@fman.io',
	'release': False,
	'files_to_filter': [
		path('src/main/resources/base/default_settings.json'),
		path('src/main/resources/osx/Info.plist')
	]
}

if is_windows():
	from build_impl.windows import exe, setup, zip, esky
elif is_osx():
	from build_impl.osx import app, sign_app, dmg, sign_dmg,\
		create_autoupdate_files, upload
elif is_linux():
	from build_impl.windows import setup

def test():
	pythonpath = pathsep.join(map(path, [
		'src/main/python', 'src/unittest/python', 'src/integrationtest/python'
	]))
	run(
		['python', '-m', 'unittest', 'fman_unittest', 'fman_integrationtest'],
		extra_env={'PYTHONPATH': pythonpath}
	)

def publish():
	if is_windows():
		exe()
		setup()
	elif is_osx():
		app()
		sign_app()
		dmg()
		sign_dmg()
		create_autoupdate_files()
		upload()
	elif is_linux():
		esky()
	else:
		raise ValueError('Unknown operating system.')

def release():
	global RELEASE
	RELEASE = True
	publish()

def clean():
	try:
		target_files = listdir(path('target'))
	except FileNotFoundError:
		return
	for f in target_files:
		if f != 'cache':
			fpath = join(path('target'), f)
			if isdir(fpath):
				rmtree(fpath, ignore_errors=True)
			elif isfile(fpath):
				remove(fpath)
			elif islink(fpath):
				unlink(fpath)

from argparse import ArgumentParser
if __name__ == '__main__':
	parser = ArgumentParser(description='Build fman.')
	parser.add_argument('cmd')
	parser.add_argument('args', metavar='arg', nargs='*')
	parser.add_argument(
		'--release', dest='release', action='store_const', const=True,
		default=False
	)
	args = parser.parse_args()
	OPTIONS['release'] = args.release
	result = globals()[args.cmd](*args.args)
	if result:
		print(result)