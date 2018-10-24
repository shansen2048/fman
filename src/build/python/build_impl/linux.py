from build_impl import copy_python_library
from fbs import path, SETTINGS
from os import remove
from shutil import rmtree
from subprocess import check_output, check_call, DEVNULL

import re

def postprocess_exe():
	rmtree(path('${core_plugin_in_freeze_dir}/bin/mac'))
	rmtree(path('${core_plugin_in_freeze_dir}/bin/windows'))
	# Roboto Bold is only used on Windows. For reasons not yet known, loading
	# fonts sometimes fails. (A known case is that Open Sans fails to load on
	# some user's Windows systems - see fman issue #480). Remove the unused font
	# to avoid potential problems, improve startup performance and decrease
	# fman's download size.
	# (Also note that a more elegant solution would be to only place
	# Open Sans.ttf in src/main/resources/*linux*/Plugins/Core. But the current
	# implementation cannot handle multiple dirs .../resources/main,
	# .../resources/linux for one plugin.)
	remove(path('${core_plugin_in_freeze_dir}/Roboto Bold.ttf'))
	copy_python_library('send2trash', path('${core_plugin_in_freeze_dir}'))

def preset_gpg_passphrase():
	check_call([
		SETTINGS['gpg_preset_passphrase'], '--preset',
		'--passphrase', SETTINGS['gpg_pass'],
		_get_keygrip(SETTINGS['gpg_key'])
	], stdout=DEVNULL)

def _get_keygrip(pubkey_id):
	output = check_output(
		['gpg2', '--with-keygrip', '-K', pubkey_id], universal_newlines=True
	)
	lines = output.split('\n')
	for i, line in enumerate(lines):
		if line.endswith('[S]'):
			keygrip_line = lines[i + 1]
			m = re.match(r' +Keygrip = ([A-Z0-9]{40})', keygrip_line)
			if not m:
				raise RuntimeError('Unexpected output: ' + keygrip_line)
			return m.group(1)
	raise RuntimeError('Keygrip not found. Output was:\n' + output)