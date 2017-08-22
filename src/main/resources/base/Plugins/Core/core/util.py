from os import listdir
from os.path import join

def strformat_dict_values(dict_, replacements):
	result = {}
	def replace(value):
		if isinstance(value, str):
			return value.format(**replacements)
		return value
	for key, value in dict_.items():
		if isinstance(value, list):
			value = list(map(replace, value))
		else:
			value = replace(value)
		result[key] = value
	return result

def listdir_absolute(dir_path):
	return [join(dir_path, file_name) for file_name in listdir(dir_path)]