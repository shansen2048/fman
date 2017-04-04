from fman.impl.plugins import SETTINGS_PLUGIN_NAME
from fman.util import listdir_absolute
from os.path import isdir, basename

def find_plugin_dirs(shipped_plugins, thirdparty_plugins, user_plugins):
	result = _list_plugins(shipped_plugins)
	result.extend(_list_plugins(thirdparty_plugins))
	settings_plugin = None
	for plugin in _list_plugins(user_plugins):
		if basename(plugin) == SETTINGS_PLUGIN_NAME:
			settings_plugin = plugin
		else:
			result.append(plugin)
	if settings_plugin:
		result.append(settings_plugin)
	return result

def _list_plugins(dir_path):
	try:
		return list(filter(isdir, listdir_absolute(dir_path)))
	except FileNotFoundError:
		return []