from os.path import splitext, join

class ConfigFileLocator:
	def __init__(self, plugin_dirs, platform):
		self._plugin_dirs = plugin_dirs
		self._platform = platform
	def __call__(self, file_name):
		base, ext = splitext(file_name)
		platform_specific_name = '%s (%s)%s' % (base, self._platform, ext)
		result = []
		for plugin_dir in self._plugin_dirs:
			result.append(join(plugin_dir, file_name))
			result.append(join(plugin_dir, platform_specific_name))
		return result