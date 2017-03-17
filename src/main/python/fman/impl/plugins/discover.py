from fman.impl.plugins import USER_PLUGIN_NAME
from fman.util import listdir_absolute
from os.path import basename, isdir, join

def find_plugin_dirs(shipped_plugins_dir, installed_plugins_dir):
	shipped_plugins = _list_plugins(shipped_plugins_dir)
	installed_plugins = [
		plugin for plugin in _list_plugins(installed_plugins_dir)
		if basename(plugin) != USER_PLUGIN_NAME
	]
	result = shipped_plugins + installed_plugins
	user_plugin = join(installed_plugins_dir, USER_PLUGIN_NAME)
	if isdir(user_plugin):
		result.append(user_plugin)
	return result

def _list_plugins(dir_path):
	try:
		return list(filter(isdir, listdir_absolute(dir_path)))
	except FileNotFoundError:
		return []