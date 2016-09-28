from build_impl import path, run, is_windows, is_mac, is_linux, OPTIONS, \
	read_filter
from os import unlink, listdir, remove, pathsep
from os.path import join, isdir, isfile, islink
from shutil import rmtree

OPTIONS.update({
	'version': read_filter()['version'],
	'local_staticfiles_dir': '/Users/michael/dev/fman.io/static',
	'server_staticfiles_dir': '/home/fman/src/static',
	'server_user': 'fman@fman.io',
	'files_to_filter': [
		path('src/main/resources/base/constants.json'),
		path('src/main/resources/mac/Info.plist')
	]
})

if is_windows():
	from build_impl.windows import exe, installer, zip, sign_exe, \
		sign_installer, add_installer_manifest
elif is_mac():
	from build_impl.mac import app, sign_app, dmg, sign_dmg,\
		create_autoupdate_files, upload
elif is_linux():
	from build_impl.linux import esky

def test():
	pythonpath = pathsep.join(map(path, [
		'src/main/python', 'src/unittest/python', 'src/integrationtest/python',
		'src/main/resources/base/Plugins/Core'
	]))
	run(
		['python', '-m', 'unittest', 'fman_unittest', 'fman_integrationtest'],
		extra_env={'PYTHONPATH': pythonpath}
	)

def publish():
	if is_windows():
		exe()
		sign_exe()
		installer()
		add_installer_manifest()
		sign_installer()
	elif is_mac():
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
	OPTIONS['release'] = True
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