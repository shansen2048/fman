from fman import PLATFORM, load_json, show_alert, show_status_message
from subprocess import Popen, check_output

import os

def open_file_with_app(file_, app):
	if PLATFORM == 'Mac':
		Popen(['/usr/bin/open', '-a', app, file_])
	else:
		Popen([app, file_])

def open_terminal_in_directory(dir_path):
	settings = load_json('Core Settings.json', default={})
	if PLATFORM == 'Mac':
		open_file_with_app(dir_path, settings['terminal_app'])
	elif PLATFORM == 'Windows':
		Popen('start ' + settings['terminal_app'], shell=True, cwd=dir_path)
	elif PLATFORM == 'Linux':
		terminal_app = settings.get('terminal_app', None)
		if not terminal_app:
			if is_gnome_based():
				terminal_app = 'gnome-terminal'
			elif is_kde_based():
				terminal_app = 'konsole'
			else:
				show_alert(
					'Could not determine the Terminal app of your linux '
					'distribution. Please configure terminal_app in '
					'"Core Settings.json".'
				)
				return
		Popen(terminal_app, cwd=dir_path)
	else:
		raise NotImplementedError(PLATFORM)

def is_gnome_based():
	curr_desktop = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
	return curr_desktop in ('unity', 'gnome')

def is_kde_based():
	curr_desktop = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
	if curr_desktop == 'kde':
		return True
	gdmsession = os.environ.get('GDMSESSION', '').lower()
	return gdmsession.startswith('kde')

def open_native_file_manager(dir_path):
	settings = load_json('Core Settings.json', default={})
	if PLATFORM == 'Mac':
		open_file_with_app(dir_path, settings['native_file_manager'])
	elif PLATFORM == 'Windows':
		Popen(
			['start', settings['native_file_manager'], dir_path], shell=True
		)
	elif PLATFORM == 'Linux':
		native_file_manager = settings.get('native_file_manager', None)
		if not native_file_manager:
			if is_gnome_based():
				native_file_manager = 'nautilus'
			elif is_kde_based():
				native_file_manager = 'dolphin'
			else:
				show_alert(
					'Could not determine the native file manager of your linux '
					'distribution. Please configure native_file_manager in '
					'"Core Settings.json".'
				)
				return
		Popen([native_file_manager, dir_path])
		if is_gnome_based():
			try:
				fpl = check_output(['dconf', 'read', _FOCUS_PREVENTION_LEVEL])
			except FileNotFoundError as dconf_not_installed:
				pass
			else:
				if fpl in (b'', b'1\n'):
					show_status_message(
						'Hint: If %s opened in the background, click '
						'<a href="https://askubuntu.com/a/594301">here</a>.'
						% native_file_manager.title(),
						timeout_secs=10
					)
	else:
		raise NotImplementedError(PLATFORM)

_FOCUS_PREVENTION_LEVEL = \
	'/org/compiz/profiles/unity/plugins/core/focus-prevention-level'