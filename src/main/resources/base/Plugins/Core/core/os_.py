from core.util import strformat_dict_values
from fman import load_json, show_alert, show_status_message, PLATFORM, save_json
from subprocess import Popen, check_output

import os

def open_terminal_in_directory(dir_path):
	gnome_default = {'args': ['gnome-terminal'], 'cwd': '{curr_dir}'}
	kde_default = {'args': ['konsole'], 'cwd': '{curr_dir}'}
	# TODO: Remove this migration after Feb, 2017.
	settings = load_json('Core Settings.json', default={})
	terminal_app = settings.pop('terminal_app', '')
	if terminal_app:
		settings['terminal'] = terminal_app
		# The migration in _run_app_from_setting(...) will now convert the
		# `terminal` string to a dict that can be used as kwargs for Popen(...).
	_run_app_from_setting('terminal', gnome_default, kde_default, dir_path)

def _run_app_from_setting(setting_name, gnome_default, kde_default, curr_dir):
	settings = load_json('Core Settings.json', default={})
	app = settings.get(setting_name, {})
	if isinstance(app, str):
		# TODO: Remove this migration after Feb, 2017.
		app = get_popen_kwargs_for_opening('{curr_dir}', with_=app)
		settings[setting_name] = app
		save_json('Core Settings.json')
	if not app:
		if is_gnome_based():
			app = gnome_default
		elif is_kde_based():
			app = kde_default
	if not app:
		show_alert(
			'Could not determine the Popen(...) arguments for opening the '
			'%s. Please configure the "%s" dictionary in "Core Settings.json". '
			'You can use "{curr_dir}" as a placeholder for the current '
			'directory.' % (setting_name.replace('_', ' '), setting_name)
		)
		return
	popen_kwargs = strformat_dict_values(app, {'curr_dir': curr_dir})
	env_not_set = popen_kwargs.get('env', None) is None
	if PLATFORM == 'Linux' and env_not_set and 'LD_LIBRARY_PATH' in os.environ:
		env = os.environ.copy()
		# PyInstaller sets LD_LIBRARY_PATH to /opt/fman.
		# We do not want this to get inherited by child processes!
		del env['LD_LIBRARY_PATH']
		popen_kwargs['env'] = env
	Popen(**popen_kwargs)

def get_popen_kwargs_for_opening(file_, with_):
	args = [with_, file_]
	if PLATFORM == 'Mac':
		args = ['/usr/bin/open', '-a'] + args
	return {'args': args}

def is_gnome_based():
	curr_desktop = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
	return curr_desktop in ('unity', 'gnome', 'x-cinnamon')

def is_kde_based():
	curr_desktop = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
	if curr_desktop == 'kde':
		return True
	gdmsession = os.environ.get('GDMSESSION', '').lower()
	return gdmsession.startswith('kde')

def open_native_file_manager(dir_path):
	gnome_default = {'args': ['nautilus', '{curr_dir}']}
	kde_default = {'args': ['dolphin', '{curr_dir}']}
	_run_app_from_setting(
		'native_file_manager', gnome_default, kde_default, dir_path
	)
	if is_gnome_based():
		try:
			fpl = check_output(['dconf', 'read', _FOCUS_PREVENTION_LEVEL])
		except FileNotFoundError as dconf_not_installed:
			pass
		else:
			if fpl in (b'', b'1\n'):
				show_status_message(
					'Hint: If your OS\'s file manager opened in the background,'
					' click <a href="https://askubuntu.com/a/594301">here</a>.',
					timeout_secs=10
				)

_FOCUS_PREVENTION_LEVEL = \
	'/org/compiz/profiles/unity/plugins/core/focus-prevention-level'